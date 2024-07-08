from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", ""))
import requests
import json

# Initialize OpenAI API key from secrets

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
            return json.dumps({
                "name": food_data["description"],
                "calories": food_data["foodNutrients"][0]["value"],  # Calories
                "protein": food_data["foodNutrients"][1]["value"],  # Protein
                "fat": food_data["foodNutrients"][2]["value"],  # Fat
                "carbs": food_data["foodNutrients"][3]["value"]  # Carbohydrates
            })
    st.session_state.logs.append(f"USDA API failed with status code: {response.status_code}")
    return json.dumps({"error": "Could not fetch nutritional information"})

# Function to generate a meal plan
def generate_meal_plan(name, health_goal, dietary_preferences, meals_per_day):
    # Placeholder implementation of meal plan generation
    meal_plan = {
        "Breakfast": "Oatmeal with fruits",
        "Lunch": "Grilled chicken salad",
        "Dinner": "Quinoa and vegetables"
    }
    return json.dumps(meal_plan)

def run_conversation(messages):
    # Define available functions for OpenAI
    functions = [
        {
            "name": "get_nutritional_info",
            "description": "Get nutritional information for a specified food item",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_item": {"type": "string", "description": "The name of the food item"}
                },
                "required": ["food_item"]
            }
        },
        {
            "name": "generate_meal_plan",
            "description": "Generate a personalized meal plan",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The user's name"},
                    "health_goal": {"type": "string", "description": "The user's health goal"},
                    "dietary_preferences": {"type": "string", "description": "The user's dietary preferences"},
                    "meals_per_day": {"type": "integer", "description": "The number of meals per day"}
                },
                "required": ["name", "health_goal", "dietary_preferences", "meals_per_day"]
            }
        }
    ]

    response = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=messages,
    functions=functions,
    function_call="auto")
    response_message = response.choices[0].message
    function_call = response_message.function_call
    # Step 2: check if the model wanted to call a function
    if function_call:
        function_name = function_call.name
        function_args = json.loads(function_call.arguments)
        if function_name == "get_nutritional_info":
            function_response = get_nutritional_info(
                food_item=function_args.get("food_item")
            )
        elif function_name == "generate_meal_plan":
            function_response = generate_meal_plan(
                name=function_args.get("name"),
                health_goal=function_args.get("health_goal"),
                dietary_preferences=function_args.get("dietary_preferences"),
                meals_per_day=function_args.get("meals_per_day")
            )
        messages.append({
            "role": "function",
            "name": function_name,
            "content": function_response,
        })  # extend conversation with function response
        second_response = client.chat.completions.create(model="gpt-3.5-turbo",
        messages=messages)  # get a new response from the model where it can see the function response
        return second_response
    return response

# Initialize session state
if "state" not in st.session_state:
    st.session_state.state = "start"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "logs" not in st.session_state:
    st.session_state.logs = []
if "usda_api_key" not in st.session_state:
    st.session_state.usda_api_key = ""
if "nutrition_info" not in st.session_state:
    st.session_state.nutrition_info = {}
if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = {}
if "total_nutrition_info" not in st.session_state:
    st.session_state.total_nutrition_info = ""

# Check for USDA API key in secrets, if not found prompt the user to enter it
if not st.secrets.get("USDA_API_KEY", ""):
    st.session_state.usda_api_key = st.text_input("Enter your USDA API key:", type="password")

# Define the dialog tree
dialog_tree = {
    "start": {
        "message": "Welcome to the AI Nutritionist! I can help you with the following:\n1. Find the nutritional content of a dish\n2. Create a personalized meal plan\n\nPlease type 'nutrition' to find nutritional content or 'meal plan' to create a meal plan.",
        "next_state": "get_action"
    },
    "get_action": {
        "message": "What would you like to do today? Type 'nutrition' for nutritional content or 'meal plan' for a personalized meal plan.",
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
        "message": "Meal Plan for {name}:\n- Goal: {health_goal}\n- Dietary Preferences: {dietary_preferences}\n- Meals per Day: {meals_per_day}\n\n{meal_plan}\n\nTotal Nutrition Information:\n{total_nutrition_info}",
        "next_state": None
    }
}

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
            return "I didn't catch that. Please type 'nutrition' for nutritional content or 'meal plan' for a personalized meal plan.", state, False
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
            # Generate a meal plan
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Generate a personalized meal plan for {st.session_state.name} with the following details: health goal - {st.session_state.health_goal}, dietary preferences - {st.session_state.dietary_preferences}, meals per day - {st.session_state.meals_per_day}. Please return the meal plan in JSON format."},
            ]
            with st.spinner('Generating meal plan...'):
                response = run_conversation(messages)

            # Extract and display the meal plan
            if response.choices:
                response_message = response.choices[0].message
                st.session_state.logs.append(f"Function call response: {response_message}")
                if response_message.role == "assistant":
                    try:
                        meal_plan = json.loads(response_message.content)
                        if "error" not in meal_plan:
                            st.session_state.meal_plan = meal_plan
                            # Get nutritional information for each meal
                            nutritional_info = {}
                            total_calories = total_protein = total_fat = total_carbs = 0
                            for meal, item in meal_plan.items():
                                nutrition_response = get_nutritional_info(item)
                                nutrition_data = json.loads(nutrition_response)
                                nutritional_info[meal] = nutrition_data
                                total_calories += nutrition_data.get("calories", 0)
                                total_protein += nutrition_data.get("protein", 0)
                                total_fat += nutrition_data.get("fat", 0)
                                total_carbs += nutrition_data.get("carbs", 0)
                            st.session_state.nutritional_info = nutritional_info
                            st.session_state.total_nutrition_info = f"Total Calories: {total_calories}\nTotal Protein: {total_protein}g\nTotal Fat: {total_fat}g\nTotal Carbohydrates: {total_carbs}g"
                            return dialog_tree[state]["message"].format(
                                name=st.session_state.name,
                                health_goal=st.session_state.health_goal,
                                dietary_preferences=st.session_state.dietary_preferences,
                                meals_per_day=st.session_state.meals_per_day,
                                meal_plan=json.dumps(meal_plan, indent=2),
                                total_nutrition_info=st.session_state.total_nutrition_info
                            ), dialog_tree[state]["next_state"], True
                        else:
                            return "I couldn't generate the meal plan. Please try again.", state, False
                    except json.JSONDecodeError:
                        return "I received an invalid response. Please try again.", state, False
            else:
                st.session_state.logs.append("Error: Couldn't generate meal plan")
                return "I couldn't generate the meal plan. Please try again.", state, False
        else:
            return "I didn't catch that. How many meals would you like to have in a day? (e.g., 3, 4, 5)", state, False
    elif state == "provide_meal_plan":
        return dialog_tree[state]["message"].format(
            name=st.session_state.name,
            health_goal=st.session_state.health_goal,
            dietary_preferences=st.session_state.dietary_preferences,
            meals_per_day=st.session_state.meals_per_day,
            meal_plan=json.dumps(st.session_state.meal_plan, indent=2),
            total_nutrition_info=st.session_state.total_nutrition_info
        ), dialog_tree[state]["next_state"], True
    return "Unexpected state.", state, False  # Ensure the function always returns a tuple

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

# JavaScript to focus on the input box
st.markdown(
    """
    <script>
    setTimeout(function() {
        var inputBox = window.parent.document.querySelector('input[type="text"]');
        if (inputBox) {
            inputBox.focus();
        }
    }, 100);
    </script>
    """,
    unsafe_allow_html=True
)

# # Display logs for debugging
# if st.session_state.logs:
#     st.subheader("Logs")
#     for log in st.session_state.logs:
#         st.write(log)
