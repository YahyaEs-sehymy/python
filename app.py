from flask import Flask, request, jsonify, session
import json
import os
import re
import spacy
from fuzzywuzzy import fuzz, process
from flask_cors import CORS
from flask_session import Session
import uuid
from langdetect import detect, LangDetectException

# Dictionnaire de traduction français-anglais pour les termes clés
fr_to_en_keywords = {
    # Indicateurs de match en direct
    'en direct': 'live',
    'actuellement': 'now',
    'maintenant': 'now',
    'score actuel': 'current score',
    'quel est le score': 'what is the score',
    'score': 'score',
    'se joue': 'live',
    'se déroule': 'live',
    'en cours': 'live',
    'comment se passe': 'how is',
    'comment se déroule': 'how is',
    
    # Indicateurs de match programmé
    'quand': 'when',
    'programmé': 'scheduled',
    'à venir': 'upcoming',
    'prochain': 'next',
    'date': 'date',
    'jouer': 'playing',
    'va jouer': 'will play',
    'jouera': 'will play',
    'aura lieu': 'will take place',
    'prévu': 'scheduled',
    'calendrier': 'schedule',
    'à quelle date': 'when',
    'à quelle heure': 'when',
    
    # Indicateurs de match terminé
    'résultat': 'result',
    'gagné': 'won',
    'perdu': 'lost',
    'score final': 'final score',
    'était': 'was',
    'final': 'final',
    'terminé': 'finished',
    'fini': 'finished',
    'a gagné': 'won',
    'a perdu': 'lost',
    'a battu': 'beat',
    'a vaincu': 'defeated',
    'qui a gagné': 'who won',
    'quel a été': 'what was',
    
    # Équipes et pays
    'maroc': 'morocco',
    'mali': 'mali',
    'comores': 'comoros',
    'zambie': 'zambia',
    'égypte': 'egypt',
    'angola': 'angola',
    'afrique du sud': 'south africa',
    'zimbabwe': 'zimbabwe',
    'nigeria': 'nigeria',
    'tanzanie': 'tanzania',
    'tunisie': 'tunisia',
    'ouganda': 'uganda',
    'algérie': 'algeria',
    'burkina faso': 'burkina faso',
    'république démocratique du congo': 'dr congo',
    'rdc': 'dr congo',
    'côte d\'ivoire': 'ivory coast',
    'guinée équatoriale': 'equatorial guinea',
    'ghana': 'ghana',
    'mozambique': 'mozambique',
    'sénégal': 'senegal',
    'gambie': 'gambia',
    'cameroun': 'cameroon',
    'guinée': 'guinea',
    'gabon': 'gabon',
    'soudan': 'sudan',
    'bénin': 'benin',
    'botswana': 'botswana',
    'mauritanie': 'mauritania',
    
    # Mots de connexion
    'contre': 'vs',
    'versus': 'vs',
    'et': 'and',
    'joue contre': 'playing against',
    'match contre': 'match against',
    'face à': 'against',
    'affronte': 'facing',
    'rencontre': 'match',
    'opposition': 'match'
}

# Dictionnaire de traduction anglais-français pour les réponses
en_to_fr_responses = {
    'Please specify the teams you are referring to, e.g., \'Morocco vs Mali.\'': 'Veuillez préciser les équipes auxquelles vous faites référence, par exemple, \'Maroc vs Mali\'.',
    'No matches found for': 'Aucun match trouvé pour',
    'No live matches found for': 'Aucun match en direct trouvé pour',
    'No finished matches found for': 'Aucun match terminé trouvé pour',
    'No scheduled matches found for': 'Aucun match programmé trouvé pour',
    'Status: Finished': 'Statut : Terminé',
    'Status: Live': 'Statut : En direct',
    'Status: Scheduled': 'Statut : Programmé',
    'Status: Scheduled for': 'Statut : Programmé pour',
    'Please enter a message.': 'Veuillez saisir un message.',
    'Sorry, there was an error processing your request. Please try again.': 'Désolé, une erreur s\'est produite lors du traitement de votre demande. Veuillez réessayer.'
}

app = Flask(__name__)
# Use environment variables for configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True

# Create session directory if it doesn't exist
session_dir = os.path.join(os.getcwd(), 'flask_session')
if not os.path.exists(session_dir):
    os.makedirs(session_dir)
app.config['SESSION_FILE_DIR'] = session_dir

Session(app)
CORS(app, supports_credentials=True)  # Enable CORS with credentials support

# Load data from db.json
def load_data():
    try:
        # Try both potential paths to find the db.json file
        paths = [
            'db.json'
        ]
        
        for path in paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    return data
        
        print("Warning: db.json not found in any expected location")
        return None
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

# Initialize spaCy - with error handling for Docker environment
try:
    nlp = spacy.load('en_core_web_sm')
except OSError:
    try:
        # If the model isn't installed, download it
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
        nlp = spacy.load('en_core_web_sm')
    except Exception as e:
        print(f"Error loading spaCy model: {e}")
        # Create a simple fallback model for basic tokenization
        nlp = spacy.blank("en")
        print("Using fallback spaCy model for basic tokenization")

# Function to extract team names from user query
def extract_teams(query):
    doc = nlp(query)
    
    # Get all data for team name matching
    data = load_data()
    all_teams = set()
    
    # Extract all team names from the live data
    if data and 'live' in data:
        for group in data['live']:
            for match in group['mlsf']:
                all_teams.add(match['team1'])
                all_teams.add(match['team2'])
    
    # Also add teams from knockout stage if available
    if data and 'knockout_stage' in data:
        for stage in ['round_of_16', 'quarter_finals', 'semi_finals', 'final']:
            if stage in data['knockout_stage']:
                for match in data['knockout_stage'][stage]:
                    all_teams.add(match['team1'])
                    all_teams.add(match['team2'])
    
    all_teams = list(all_teams)
    
    # If no teams found in data, use a fallback list of common teams
    if not all_teams:
        all_teams = [
            "Morocco", "Mali", "Comoros", "Zambia", "Egypt", "Angola", 
            "South Africa", "Zimbabwe", "Nigeria", "Tanzania", "Tunisia", 
            "Uganda", "Algeria", "Burkina Faso", "DR Congo", "Ivory Coast", 
            "Equatorial Guinea", "Ghana", "Mozambique", "Senegal", "Gambia", 
            "Cameroon", "Guinea", "Gabon", "Sudan", "Benin", "Botswana", "Mauritania"
        ]
    
    # Check for common patterns like "Team1 vs Team2" or "Team1 against Team2"
    vs_pattern = re.compile(r'([\w\s]+)\s+(?:vs|against|versus|and|v\.?|-|playing|match(?:ed)? (?:with|against))\s+([\w\s]+)', re.IGNORECASE)
    vs_match = vs_pattern.search(query)
    if vs_match:
        team1_text = vs_match.group(1).strip()
        team2_text = vs_match.group(2).strip()
        
        # Find best matches for both teams
        team1_match, score1 = process.extractOne(team1_text, all_teams, scorer=fuzz.token_sort_ratio)
        team2_match, score2 = process.extractOne(team2_text, all_teams, scorer=fuzz.token_sort_ratio)
        
        if score1 > 65 and score2 > 65:  # Lower threshold for better matching with typos
            return [team1_match, team2_match]
    
    # Handle common misspellings and abbreviations of country names
    country_aliases = {
        "ivory": "Ivory Coast",
        "cote": "Ivory Coast",
        "drc": "DR Congo",
        "congo dr": "DR Congo",
        "sa": "South Africa",
        "rsa": "South Africa",
        "eq guinea": "Equatorial Guinea",
        "burkina": "Burkina Faso",
        "bf": "Burkina Faso"
    }
    
    # Check for country aliases in the query
    for alias, full_name in country_aliases.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', query.lower()):
            if full_name in all_teams:
                return [full_name]
    
    # Extract potential team names from the query using NER
    potential_teams = []
    for ent in doc.ents:
        if hasattr(ent, 'label_') and ent.label_ in ["ORG", "GPE", "LOC"]:
            potential_teams.append(ent.text)
    
    # If no entities found, try to match words against team names
    if not potential_teams:
        for token in doc:
            if hasattr(token, 'pos_') and token.pos_ in ["PROPN", "NOUN"] and len(token.text) > 2:
                potential_teams.append(token.text)
        
        # Also try to extract consecutive proper nouns (for multi-word country names)
        for i in range(len(doc) - 1):
            if hasattr(doc[i], 'pos_') and hasattr(doc[i+1], 'pos_') and \
               doc[i].pos_ == "PROPN" and doc[i+1].pos_ == "PROPN":
                potential_teams.append(doc[i].text + " " + doc[i+1].text)
    
    # Use fuzzy matching to find the best matches for team names
    teams = []
    for team in potential_teams:
        best_match, score = process.extractOne(team, all_teams, scorer=fuzz.token_sort_ratio)
        if score > 65:  # Lower threshold for better matching with typos
            if best_match not in teams:  # Avoid duplicates
                teams.append(best_match)
    
    return teams

# Function to determine the type of question (finished, live, scheduled)
def determine_question_type(query):
    query = query.lower()
    
    # Check for live match indicators
    live_indicators = ['live', 'going', 'happening', 'now', 'current', 'playing right now', 'what is the score', 'what\'s the score']
    for indicator in live_indicators:
        if indicator in query:
            return 'live'
    
    # Check for scheduled match indicators
    scheduled_indicators = ['when', 'will', 'schedule', 'upcoming', 'soon', 'next', 'date', 'playing']
    for indicator in scheduled_indicators:
        if indicator in query:
            return 'scheduled'
    
    # Default to finished matches
    finished_indicators = ['result', 'won', 'win', 'lost', 'score', 'was', 'did', 'perform', 'final']
    for indicator in finished_indicators:
        if indicator in query:
            return 'finished'
    
    # If no clear indicators, default to checking all types
    return 'all'

# Function to find match information based on teams and status
def find_match(team1, team2=None, status_type='all'):
    data = load_data()
    if not data or 'live' not in data:
        return None
    
    matches = []
    
    for group in data['live']:
        for match in group['mlsf']:
            # If both teams are specified, check for exact match
            if team2:
                teams_match = ((match['team1'] == team1 and match['team2'] == team2) or 
                              (match['team1'] == team2 and match['team2'] == team1))
            # If only one team is specified, check if it's in the match
            else:
                teams_match = (match['team1'] == team1 or match['team2'] == team1)
            
            # Check if status matches the requested type
            status_match = (status_type == 'all' or 
                          (status_type == 'live' and match['status'] == 'live') or 
                          (status_type == 'finished' and match['status'] == 'finished') or 
                          (status_type == 'scheduled' and match['status'] == 'scheduled'))
            
            if teams_match and status_match:
                matches.append(match)
    
    return matches

# Function to format match response
def format_match_response(match):
    team1 = match['team1']
    team2 = match['team2']
    score1 = match['score1']
    score2 = match['score2']
    status = match['status']
    time = match['time']
    
    if status == 'finished':
        return f"{team1} {score1} - {score2} {team2} | Status: Finished"
    elif status == 'live':
        return f"{team1} {score1} - {score2} {team2} | Status: Live - {time}"
    else:  # scheduled
        return f"{team1} vs {team2} | Status: Scheduled for {time}" if time != "Not started" else f"{team1} vs {team2} | Status: Scheduled"

# Function to handle unclear questions
def handle_unclear_question():
    return "Please specify the teams you are referring to, e.g., 'Morocco vs Mali.'"

# Function to detect language and translate query if needed
def detect_language(text):
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        # Default to English if detection fails
        return 'en'

# Function to translate French query to English for processing
def translate_query_fr_to_en(query):
    # Convert query to lowercase for better matching
    query_lower = query.lower()
    
    # Replace French terms with English equivalents
    for fr_term, en_term in fr_to_en_keywords.items():
        query_lower = re.sub(r'\b' + re.escape(fr_term) + r'\b', en_term, query_lower, flags=re.IGNORECASE)
    
    return query_lower

# Function to translate English response to French
def translate_response_en_to_fr(response):
    # First check for exact matches in our dictionary
    for en_phrase, fr_phrase in en_to_fr_responses.items():
        if en_phrase in response:
            response = response.replace(en_phrase, fr_phrase)
    
    # Handle team names and scores in format like "Morocco 2 - 1 Egypt | Status: Finished"
    match_pattern = re.compile(r'([A-Za-z\s]+) (\d+) - (\d+) ([A-Za-z\s]+) \| Status: (.+)')
    match = match_pattern.search(response)
    if match:
        team1 = match.group(1).strip()
        score1 = match.group(2)
        score2 = match.group(3)
        team2 = match.group(4).strip()
        status = match.group(5)
        
        # Translate team names if they exist in our dictionary
        for en_team, fr_team in {v: k for k, v in fr_to_en_keywords.items() if v in ['morocco', 'egypt', 'algeria', 'tunisia', 'senegal', 'ivory coast', 'cameroon', 'ghana', 'nigeria', 'south africa', 'dr congo', 'mali', 'burkina faso', 'guinea', 'zambia', 'uganda', 'tanzania', 'comoros', 'angola', 'zimbabwe', 'equatorial guinea', 'gambia', 'gabon', 'sudan', 'mozambique']}.items():
            if team1.lower() == en_team:
                team1 = fr_team.title()
            if team2.lower() == en_team:
                team2 = fr_team.title()
        
        # Translate status
        status_fr = status
        for en_status, fr_status in en_to_fr_responses.items():
            if status in en_status:
                status_fr = fr_status
                break
        
        response = f"{team1} {score1} - {score2} {team2} | {status_fr}"
    
    # Handle scheduled matches format like "Morocco vs Egypt | Status: Scheduled for 2023-01-01"
    scheduled_pattern = re.compile(r'([A-Za-z\s]+) vs ([A-Za-z\s]+) \| Status: (.+)')
    match = scheduled_pattern.search(response)
    if match:
        team1 = match.group(1).strip()
        team2 = match.group(2).strip()
        status = match.group(3)
        
        # Translate team names
        for en_team, fr_team in {v: k for k, v in fr_to_en_keywords.items() if v in ['morocco', 'egypt', 'algeria', 'tunisia', 'senegal', 'ivory coast', 'cameroon', 'ghana', 'nigeria', 'south africa', 'dr congo', 'mali', 'burkina faso', 'guinea', 'zambia', 'uganda', 'tanzania', 'comoros', 'angola', 'zimbabwe', 'equatorial guinea', 'gambia', 'gabon', 'sudan', 'mozambique']}.items():
            if team1.lower() == en_team:
                team1 = fr_team.title()
            if team2.lower() == en_team:
                team2 = fr_team.title()
        
        # Translate status
        status_fr = status
        for en_status, fr_status in en_to_fr_responses.items():
            if status.startswith(en_status):
                status_fr = status.replace(en_status, fr_status)
                break
        
        response = f"{team1} vs {team2} | {status_fr}"
    
    # Handle "No matches found" responses
    no_matches_pattern = re.compile(r'No (.*?) matches found for (.+)\.')
    match = no_matches_pattern.search(response)
    if match:
        match_type = match.group(1)
        teams = match.group(2)
        
        # Translate match type
        match_type_fr = match_type
        if match_type == 'live':
            match_type_fr = 'en direct'
        elif match_type == 'finished':
            match_type_fr = 'terminés'
        elif match_type == 'scheduled':
            match_type_fr = 'programmés'
        
        # Translate team names in the format "Team1 vs Team2"
        teams_parts = teams.split(' vs ')
        translated_teams = []
        for team in teams_parts:
            translated = team
            for en_team, fr_team in {v: k for k, v in fr_to_en_keywords.items() if v in ['morocco', 'egypt', 'algeria', 'tunisia', 'senegal', 'ivory coast', 'cameroon', 'ghana', 'nigeria', 'south africa', 'dr congo', 'mali', 'burkina faso', 'guinea', 'zambia', 'uganda', 'tanzania', 'comoros', 'angola', 'zimbabwe', 'equatorial guinea', 'gambia', 'gabon', 'sudan', 'mozambique']}.items():
                if team.lower() == en_team:
                    translated = fr_team.title()
                    break
            translated_teams.append(translated)
        
        response = f"Aucun match {match_type_fr} trouvé pour {' vs '.join(translated_teams)}."
    
    return response

# Function to process user query and generate response
def process_query(query):
    # Detect language
    lang = detect_language(query)
    
    # If French, translate to English for processing
    original_lang = lang
    if lang == 'fr':
        query = translate_query_fr_to_en(query)
    
    # Extract teams from the query
    teams = extract_teams(query)
    
    # Determine question type
    question_type = determine_question_type(query)
    
    # Check for specific score-related questions
    score_patterns = [
        r"(?:what(?:'s| is) the|current) score (?:of|for|between) (.*?)(?:\?|$)",
        r"score (?:of|for|between) (.*?)(?:\?|$)"
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match and not teams:
            teams_text = match.group(1).strip()
            # Try to extract teams from this specific text
            potential_teams = teams_text.split(' and ')
            if len(potential_teams) == 1:
                potential_teams = teams_text.split(' vs ')
            if len(potential_teams) == 1:
                potential_teams = teams_text.split(' against ')
            
            if len(potential_teams) == 2:
                data = load_data()
                all_teams = set()
                if data and 'live' in data:
                    for group in data['live']:
                        for match in group['mlsf']:
                            all_teams.add(match['team1'])
                            all_teams.add(match['team2'])
                all_teams = list(all_teams)
                
                team1_match, score1 = process.extractOne(potential_teams[0].strip(), all_teams, scorer=fuzz.token_sort_ratio)
                team2_match, score2 = process.extractOne(potential_teams[1].strip(), all_teams, scorer=fuzz.token_sort_ratio)
                
                if score1 > 70 and score2 > 70:
                    teams = [team1_match, team2_match]
                    # For score questions, prioritize live matches, then finished
                    question_type = 'live'
    
    # If no teams found, return a prompt for more information
    response = handle_unclear_question()
    if not teams:
        response = handle_unclear_question()
    else:
        # If one team found, find matches involving that team
        if len(teams) == 1:
            matches = find_match(teams[0], status_type=question_type)
        # If two teams found, find matches between those teams
        elif len(teams) >= 2:
            # Try to find matches with the exact order first
            matches = find_match(teams[0], teams[1], status_type=question_type)
            
            # If no matches found, try the reverse order
            if not matches or len(matches) == 0:
                matches = find_match(teams[1], teams[0], status_type=question_type)
        
        # If no matches found, return appropriate message
        if not matches or len(matches) == 0:
            if question_type == 'all':
                response = f"No matches found for {' vs '.join(teams)}."
            else:
                response = f"No {question_type} matches found for {' vs '.join(teams)}."
        else:
            # Return formatted response for the first match found
            response = format_match_response(matches[0])
    
    # If original query was in French, translate the response back to French
    if original_lang == 'fr':
        response = translate_response_en_to_fr(response)
    
    return response

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'response': 'Please enter a message.'})
        
        # Get or create session ID
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            session['conversation'] = []
        
        # Process the user's query
        response = process_query(user_message)
        
        # Store the conversation in session
        conversation = session.get('conversation', [])
        conversation.append({'message': user_message, 'isUser': True})
        conversation.append({'message': response, 'isUser': False})
        session['conversation'] = conversation
        
        return jsonify({
            'response': response,
            'conversation': conversation
        })
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({
            'response': 'Sorry, there was an error processing your request. Please try again.',
            'error': str(e)
        }), 500

@app.route('/query', methods=['POST', 'OPTIONS'])
def query():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'response': 'Please enter a message.'})
        
        # Get or create session ID
        session_id = session.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
            session['conversation'] = []
        
        # Process the user's query
        response = process_query(user_message)
        
        # Store the conversation in session
        conversation = session.get('conversation', [])
        conversation.append({'message': user_message, 'isUser': True})
        conversation.append({'message': response, 'isUser': False})
        session['conversation'] = conversation
        
        return jsonify({
            'response': response,
            'conversation': conversation
        })
    except Exception as e:
        print(f"Error in query endpoint: {e}")
        return jsonify({
            'response': 'Sorry, there was an error processing your request. Please try again.',
            'error': str(e)
        }), 500

@app.route('/')
def index():
    return "AFCON 2025 Chatbot API is running!"

@app.route('/api/conversation', methods=['GET'])
def get_conversation():
    # Get conversation from session
    conversation = session.get('conversation', [])
    return jsonify({'conversation': conversation})

@app.route('/api/conversation/clear', methods=['POST'])
def clear_conversation():
    # Clear conversation in session
    session['conversation'] = []
    return jsonify({'status': 'success', 'message': 'Conversation cleared'})

@app.route('/health', methods=['GET'])
def health_check():
    # Add a health check endpoint for Docker
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Use environment variables for host and port if available
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5555))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)