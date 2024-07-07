from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
import warnings

# Suppress specific deprecation warning
warnings.filterwarnings("ignore", message=".*st.experimental_set_query_params.*")

# Title and description
st.title("💬 AI-Powered Nutritionist Chatbot")
st.write(
    "Welcome to the AI Nutritionist! This chatbot uses OpenAI's GPT-3.5-turbo model to generate personalized meal plans based on your input. "
    "To use this app, please provide some basic information about yourself."
)

# Initialize OpenAI API key from secrets

# Initialize session state
if "state" not in st.session_state:
    st.session_state.state = "start"
if "name" not in st.session_state:
    st.session_state.name = ""
if "health_goal" not in st.session_state:
    st.session_state.health_goal = ""
if "dietary_preferences" not in st.session_state:
    st.session_state.dietary_preferences = ""
if "meal_count" not in st.session_state:
    st.session_state.meal_count = ""
if "responses" not in st.session_state:
    st.session_state.responses = []
if "messages" not in st.session_state:
    st.session_state.messages = []

# Define the dialog tree with polite messages
dialog_tree = {
    "start": {
        "message": "Let's get started with your personalized meal plan. What is your name?",
        "next_state": "get_name"
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
        "next_state": "provide_meal_plan"
    },
    "provide_meal_plan": {
        "message": "Meal Plan for {name}:\n- Goal: {health_goal}\n- Dietary Preferences: {dietary_preferences}\n- Meals per Day: {meal_count}",
        "next_state": None
    }
}

# Function to handle dialog
def handle_dialog(state, user_input=None):
    if state == "start":
        return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
    elif state == "get_name":
        name = extract_entity(user_input, "name")
        if name:
            st.session_state.name = name
            return dialog_tree[state]["message"].format(name=st.session_state.name), dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. Could you please tell me your name?", state, False
    elif state == "get_health_goal":
        health_goal = extract_entity(user_input, "health_goal")
        if health_goal:
            st.session_state.health_goal = health_goal
            return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. Could you please tell me your main health goal?", state, False
    elif state == "get_dietary_preferences":
        dietary_preferences = extract_entity(user_input, "dietary_preferences")
        if dietary_preferences:
            st.session_state.dietary_preferences = dietary_preferences
            return dialog_tree[state]["message"], dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. Do you have any dietary preferences or restrictions?", state, False
    elif state == "provide_meal_plan":
        meal_count = extract_entity(user_input, "meal_count")
        if meal_count:
            st.session_state.meal_count = meal_count
            return dialog_tree[state]["message"].format(
                name=st.session_state.name,
                health_goal=st.session_state.health_goal,
                dietary_preferences=st.session_state.dietary_preferences,
                meal_count=st.session_state.meal_count
            ), dialog_tree[state]["next_state"], True
        else:
            return "I didn't catch that. How many meals would you like to have in a day?", state, False

# Function to generate meal plan using OpenAI
def generate_meal_plan():
    prompt = f"Create a personalized meal plan for someone with the following details:\n\nName: {st.session_state.name}\nGoal: {st.session_state.health_goal}\nDietary Preferences: {st.session_state.dietary_preferences}\nMeals per Day: {st.session_state.meal_count}"
    response = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=[{"role": "system", "content": prompt}],
    max_tokens=300)
    return response.choices[0].message.content

# Function to extract intent and entities for developer insight
def extract_intent_entities(text):
    prompt = f"Extract the intent and entities from the following text:\n\n{text}\n\nProvide the result in the following JSON format:\n{{\"intent\": \"<intent>\", \"entities\": [{{\"entity\": \"<entity>\", \"type\": \"<type>\"}}]}}"
    response = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=[{"role": "system", "content": prompt}],
    max_tokens=100)
    return response.choices[0].message.content

# Function to extract specific entity from the text and validate it
def extract_entity(text, entity_type):
    prompt = f"Extract the {entity_type} from the following text:\n\n{text}\n\nProvide only the {entity_type}."
    response = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=[{"role": "system", "content": prompt}],
    max_tokens=50)
    extracted_entity = response.choices[0].message.content.strip()
    if extracted_entity and validate_entity(extracted_entity, entity_type):
        return extracted_entity
    return None

# Function to validate the extracted entity
def validate_entity(entity, entity_type):
    if entity_type == "name":
        return entity.isalpha() and len(entity) > 1  # Name should be alphabetic and more than one character
    if entity_type == "health_goal":
        valid_goals = ["lose weight", "build muscle", "maintain health"]
        return any(goal in entity.lower() for goal in valid_goals)
    if entity_type == "dietary_preferences":
        valid_preferences = ["vegan", "vegetarian", "no dairy", "none"]
        return any(pref in entity.lower() for pref in valid_preferences)
    if entity_type == "meal_count":
        return entity.isdigit() and 1 <= int(entity) <= 10  # Meal count should be a number between 1 and 10
    return False

# Display the existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Function to handle user responses
def handle_user_response(prompt):
    if st.session_state.state:
        user_input = prompt
        st.session_state.messages.append({"role": "user", "content": user_input})
        message, next_state, valid_input = handle_dialog(st.session_state.state, user_input)
        st.session_state.messages.append({"role": "assistant", "content": message})
        if valid_input:
            st.session_state.state = next_state
        st.experimental_rerun()

# Display final meal plan if in the final state
if st.session_state.state == "provide_meal_plan":
    meal_plan = generate_meal_plan()
    st.session_state.messages.append({"role": "assistant", "content": meal_plan})
    st.session_state.state = None

    # Extract and display intent and entities for developer insight
    insights = extract_intent_entities(meal_plan)
    st.session_state.messages.append({"role": "assistant", "content": f"Developer Insights:\n{insights}"})

# Handle user input at the bottom of the page
if prompt := st.chat_input("What is up?"):
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
