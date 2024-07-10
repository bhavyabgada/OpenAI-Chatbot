from openai import OpenAI
import streamlit as st
import requests
import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))

# Initialize vector store for liked recipes
if "vector_store" not in st.session_state:
    st.session_state.vector_store = []

# Function to get nutritional information from USDA Food Data Central API
def get_nutritional_info(food_item):
    api_key = st.secrets.get("USDA_API_KEY", "")
    if not api_key:
        api_key = st.session_state.usda_api_key

    st.session_state.logs.append(f"Calling get_nutritional_info with food_item={food_item} and api_key={api_key}")
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?query={food_item}&pageSize=1&api_key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        st.session_state.logs.append(f"USDA API response: {data}")
        if data["foods"]:
            food_data = data["foods"][0]
            nutrients = {nutrient["nutrientName"]: nutrient["value"] for nutrient in food_data["foodNutrients"]}
            return {
                "name": food_data["description"],
                "calories": nutrients.get("Energy", 0),
                "protein": nutrients.get("Protein", 0),
                "fat": nutrients.get("Total lipid (fat)", 0),
                "carbs": nutrients.get("Carbohydrate, by difference", 0)
            }
    st.session_state.logs.append(f"USDA API failed with status code: {response.status_code}")
    return {"error": "Could not fetch nutritional information"}

# Function to generate a meal plan using OpenAI and user preferences
def generate_meal_plan(name, health_goal, dietary_preferences, meals_per_day):
    preferred_recipes = recommend_recipes_from_preferences()
    if preferred_recipes:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that creates personalized meal plans using user preferences."},
            {"role": "user", "content": f"Create a personalized meal plan for {name} with the following details:\nHealth Goal: {health_goal}\nDietary Preferences: {dietary_preferences}\nMeals per Day: {meals_per_day}\nInclude some of these preferred recipes: {preferred_recipes}"}
        ]
    else:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that creates personalized meal plans."},
            {"role": "user", "content": f"Create a personalized meal plan for {name} with the following details:\nHealth Goal: {health_goal}\nDietary Preferences: {dietary_preferences}\nMeals per Day: {meals_per_day}"}
        ]
    response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
    meal_plan = response.choices[0].message.content
    st.session_state.logs.append(f"Generated meal plan: {meal_plan}")
    return meal_plan

# Function to parse meal plan and extract food items
def extract_food_items(meal_plan):
    food_items = re.findall(r"(?<=:).*?(?=\n|$)", meal_plan)
    st.session_state.logs.append(f"Extracted food items: {food_items}")
    return [item.strip() for item in food_items if item.strip()]

# Function to calculate total nutritional values
def calculate_total_nutrition(nutritional_data_list):
    total_nutrition = {
        "calories": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0
    }
    for data in nutritional_data_list:
        if "error" not in data:
            total_nutrition["calories"] += data.get("calories", 0)
            total_nutrition["protein"] += data.get("protein", 0)
            total_nutrition["fat"] += data.get("fat", 0)
            total_nutrition["carbs"] += data.get("carbs", 0)
    st.session_state.logs.append(f"Total nutrition calculated: {total_nutrition}")
    return total_nutrition

# Function to suggest recipes based on ingredients
def suggest_recipes(ingredients):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that suggests recipes based on ingredients."},
        {"role": "user", "content": f"Suggest some recipes using the following ingredients: {ingredients}"}
    ]
    response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
    recipes = response.choices[0].message.content
    st.session_state.logs.append(f"Suggested recipes: {recipes}")
    return recipes

# Function to store liked recipe in vector store
def store_liked_recipe(recipe):
    st.session_state.vector_store.append(recipe)
    st.session_state.logs.append(f"Stored liked recipe: {recipe}")

# Function to recommend recipes based on stored preferences
def recommend_recipes_from_preferences():
    if st.session_state.vector_store:
        return st.session_state.vector_store
    return None

# Function to handle dialog
def handle_dialog(state, user_input=None):
    st.session_state.logs.append(f"Handling dialog for state: {state}, user_input: {user_input}")
    if state == "start":
        return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
    elif state == "get_action":
        st.session_state.action = user_input.lower()
        if st.session_state.action in dialog_tree["process_action"]:
            return dialog_tree["process_action"][st.session_state.action]["message"], dialog_tree["process_action"][st.session_state.action]["next_state"], True
        else:
            return "I didn't catch that. Please type 'nutrition' for nutritional content, 'meal plan' for a personalized meal plan, or 'recipe' to suggest a recipe.", state, False
    elif state == "provide_nutrition_info":
        # Extract food item and portion size
        parts = user_input.split(" of ")
        if len(parts) == 2:
            st.session_state.food_item = parts[1].strip()
            st.session_state.portion_size = parts[0].strip()
        else:
            st.session_state.food_item = user_input.strip()
            st.session_state.portion_size = "1 serving"

        # Generate a response using OpenAI's function calling
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Extract the food item and portion size from the user's input and call the 'get_nutritional_info' function with these details: {user_input}. Please return the response in JSON format."},
        ]
        with st.spinner('Fetching nutritional information...'):
            response = run_conversation(messages)

        # Extract and display the nutrition information
        if response.choices:
            response_message = response.choices[0].message
            st.session_state.logs.append(f"Function call response: {response_message}")
            if response_message.role == "assistant":
                try:
                    nutrition_info = json.loads(response_message.content)
                    if "error" not in nutrition_info:
                        st.session_state.nutrition_info = nutrition_info
                        return dialog_tree[state]["message"].format(
                            food_item=st.session_state.food_item,
                            portion_size=st.session_state.portion_size,
                            nutrition_info=json.dumps(nutrition_info, indent=2)
                        ), dialog_tree[state]["next_state"], True
                    else:
                        return "I couldn't fetch the nutritional information. Please try again.", state, False
                except json.JSONDecodeError:
                    return "I received an invalid response. Please try again.", state, False
        else:
            st.session_state.logs.append("Error: Couldn't fetch nutritional information")
            return "I couldn't fetch the nutritional information. Please try again.", state, False
    elif state == "get_name":
        st.session_state.name = user_input
        if st.session_state.name:
            return dialog_tree[state]["message"].format(name=st.session_state.name), dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. Could you please tell me your name?", state, False
    elif state == "get_health_goal":
        st.session_state.health_goal = user_input
        if st.session_state.health_goal:
            return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. Could you please tell me your health goal? (e.g., lose weight, build muscle, maintain health)", state, False
    elif state == "get_dietary_preferences":
        st.session_state.dietary_preferences = user_input
        if st.session_state.dietary_preferences:
            return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. Do you have any dietary preferences or restrictions? (e.g., vegan, vegetarian, no dairy)", state, False
    elif state == "get_meals_per_day":
        st.session_state.meals_per_day = user_input
        if st.session_state.meals_per_day:
            st.session_state.meal_plan = generate_meal_plan(
                st.session_state.name,
                st.session_state.health_goal,
                st.session_state.dietary_preferences,
                st.session_state.meals_per_day
            )

            # Extract food items from the meal plan
            food_items = extract_food_items(st.session_state.meal_plan)
            nutritional_data_list = []
            for item in food_items:
                nutritional_data = get_nutritional_info(item)
                nutritional_data_list.append(nutritional_data)

            # Calculate total nutritional values
            total_nutrition = calculate_total_nutrition(nutritional_data_list)
            st.session_state.total_nutrition = total_nutrition

            return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. How many meals would you like to have in a day? (e.g., 3, 4, 5)", state, False
    elif state == "provide_meal_plan":
        return dialog_tree[state]["message"].format(
            name=st.session_state.name,
            health_goal=st.session_state.health_goal,
            dietary_preferences=st.session_state.dietary_preferences,
            meals_per_day=st.session_state.meals_per_day,
            meal_plan=st.session_state.meal_plan
        ) + f"\n\nTotal Nutrition for the day:\nCalories: {st.session_state.total_nutrition['calories']} kcal\nProtein: {st.session_state.total_nutrition['protein']} g\nFat: {st.session_state.total_nutrition['fat']} g\nCarbs: {st.session_state.total_nutrition['carbs']} g", dialog_tree[state]["next_state"], True
    elif state == "suggest_recipe":
        st.session_state.ingredients = user_input
        recipes = suggest_recipes(user_input)
        st.session_state.suggested_recipes = recipes
        return recipes, "store_recipe", True
    elif state == "store_recipe":
        if user_input.lower() == "yes":
            store_liked_recipe(st.session_state.suggested_recipes)
            return "Recipe stored successfully!", "start", True
        else:
            return "Recipe not stored.", "start", True
    return "Unexpected state.", state, False  # Ensure the function always returns a tuple

# Initialize session state
if "state" not in st.session_state:
    st.session_state.state = "start"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "logs" not in st.session_state:
    st.session_state.logs = []
if "usda_api_key" not in st.session_state:
    st.session_state.usda_api_key = ""
if "food_item" not in st.session_state:
    st.session_state.food_item = ""
if "portion_size" not in st.session_state:
    st.session_state.portion_size = ""
if "nutrition_info" not in st.session_state:
    st.session_state.nutrition_info = {}
if "action" not in st.session_state:
    st.session_state.action = ""
if "name" not in st.session_state:
    st.session_state.name = ""
if "health_goal" not in st.session_state:
    st.session_state.health_goal = ""
if "dietary_preferences" not in st.session_state:
    st.session_state.dietary_preferences = ""
if "meals_per_day" not in st.session_state:
    st.session_state.meals_per_day = ""
if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = ""
if "total_nutrition" not in st.session_state:
    st.session_state.total_nutrition = {}
if "ingredients" not in st.session_state:
    st.session_state.ingredients = ""
if "suggested_recipes" not in st.session_state:
    st.session_state.suggested_recipes = ""

# Check for USDA API key in secrets, if not found prompt the user to enter it
if not st.secrets.get("USDA_API_KEY", ""):
    st.session_state.usda_api_key = st.text_input("Enter your USDA API key:", type="password")

# Define the dialog tree
dialog_tree = {
    "start": {
        "message": "Welcome to the AI Nutritionist! I can help you with the following:\n1. Find the nutritional content of a dish\n2. Create a personalized meal plan\n3. Suggest a recipe based on ingredients\n\nPlease type 'nutrition' to find nutritional content, 'meal plan' to create a meal plan, or 'recipe' to suggest a recipe.",
        "next_state": "get_action"
    },
    "get_action": {
        "message": "What would you like to do today? Type 'nutrition' for nutritional content, 'meal plan' for a personalized meal plan, or 'recipe' to suggest a recipe.",
        "next_state": "process_action"
    },
    "process_action": {
        "nutrition": {
            "message": "Please tell me the name and portion size of the dish you want to find the nutritional content for.",
            "next_state": "provide_nutrition_info"
        },
        "meal plan": {
            "message": "Let's get started with your personalized meal plan. What is your name?",
            "next_state": "get_name"
        },
        "recipe": {
            "message": "Please enter the ingredients you have (comma separated):",
            "next_state": "suggest_recipe"
        }
    },
    "provide_nutrition_info": {
        "message": "Nutritional Information for {food_item} ({portion_size}):\n{nutrition_info}",
        "next_state": None
    },
    "get_name": {
        "message": "Hi {name}! What is your main health goal? (e.g., lose weight, build muscle, maintain health)",
        "next_state": "get_health_goal"
    },
    "get_health_goal": {
        "message": "Great! Do you have any dietary preferences or restrictions? (e.g., vegan, vegetarian, no dairy)",
        "next_state": "get_dietary_preferences"
    },
    "get_dietary_preferences": {
        "message": "Got it. How many meals would you like to have in a day? (e.g., 3, 4, 5)",
        "next_state": "get_meals_per_day"
    },
    "get_meals_per_day": {
        "message": "Thank you! Based on the information provided, here is your personalized meal plan.",
        "next_state": "provide_meal_plan"
    },
    "provide_meal_plan": {
        "message": "Meal Plan for {name}:\n- Goal: {health_goal}\n- Dietary Preferences: {dietary_preferences}\n- Meals per Day: {meals_per_day}\n\n{meal_plan}",
        "next_state": None
    },
    "suggest_recipe": {
        "message": "Here are some recipes you can make with the ingredients: {suggested_recipes}\nDo you want to store this recipe? (yes/no)",
        "next_state": "store_recipe"
    },
    "store_recipe": {
        "message": "Do you want to store this recipe? (yes/no)",
        "next_state": None
    }
}

# Display existing chat messages
st.title("🍽️ AI-Powered Nutritionist Chatbot")
st.write("This bot provides a detailed meal plan based on your dietary preferences and health goals or nutritional content of dishes.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
def handle_user_response(prompt):
    if st.session_state.state:
        user_input = prompt
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.logs.append(f"User input: {user_input}")
        message, next_state, valid_input = handle_dialog(st.session_state.state, user_input)
        st.session_state.messages.append({"role": "assistant", "content": message})
        if valid_input:
            st.session_state.state = next_state
        st.experimental_rerun()

# Handle user input at the bottom of the page
if prompt := st.chat_input("Your response:"):
    handle_user_response(prompt)

# # Display logs for debugging
# if st.session_state.logs:
#     st.subheader("Logs")
#     for log in st.session_state.logs:
#         st.write(log)
