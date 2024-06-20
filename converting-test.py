import re
from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep

@inlineCallbacks
def main(session, details):
     # Example usage
    text = '''Here is your workout routine:
    <list>
    1. Bench Press; 3 sets; 8-12 reps
    2. Seated Row; 3 sets; 8-12 reps
    3. Squats; 4 sets; 8-12 reps
    1. Bench Press; 3 sets; 8-12 reps
    2. Seated Row; 3 sets; 8-12 reps
    3. Squats; 4 sets; 8-12 reps
    1. Bench Press; 3 sets; 8-12 reps
    2. Seated Row; 3 sets; 8-12 reps
    3. Squats; 4 sets; 8-12 reps
    </list>
    Enjoy your workout!'''

    cleaned_text = process_workout_text(session, text)
    print("Cleaned text without the list:")
    print(cleaned_text)
    yield session.call("ridk.fitbot.setResponse", cleaned_text)
    yield session.call("ridk.fitbot.setStatus", "Listening", True)
    yield sleep(3)
    yield session.call("ridk.fitbot.setStatus", "Processing", True)
    yield sleep(1)
    yield session.call("ridk.fitbot.setStatus", "Speaking", True)
    yield sleep(2.5)
    yield session.call("ridk.fitbot.setStatus", "Listening", True)
    yield session.call("ridk.fitbot.setResponse", "**This is a new response**\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\nThis is a new response\n with multiple lines.\n")
    yield session.leave()
     
def process_workout_text(session, text):
    # Define regex to match the <list>...</list> content
    list_pattern = re.compile(r'<list>(.*?)</list>', re.DOTALL)
    
    # Extract the list content
    list_match = list_pattern.search(text)
    if list_match:
        list_content = list_match.group(1).strip()
        
        # Remove the list content from the original text
        cleaned_text = list_pattern.sub('', text).strip()
        
        # Parse the list into a structured format
        exercises = []
        for line in list_content.split('\n'):
            if line.strip():
                parts = line.split(';')
                if len(parts) == 3:
                    exercise = parts[0].strip()
                    sets = parts[1].strip()
                    reps = parts[2].strip()
                    exercises.append((exercise, sets, reps))
        
        # Create the HTML content with CSS to center the table
        routineHTML = '''
                <table>
                <tr>
                    <th>Exercise</th>
                    <th>Sets</th>
                    <th>Reps</th>
                </tr>
                '''
        for exercise in exercises:
            routineHTML += f'''
            <tr>
                <td>{exercise[0]}</td>
                <td>{exercise[1]}</td>
                <td>{exercise[2]}</td>
            </tr>
            '''
        routineHTML += "</table>"
        
        session.call("ridk.fitbot.setRoutine", routineHTML)
        
        return cleaned_text
    else:
        return text
    
wamp = Component(
	transports=[{
		"url": "ws://wamp.robotsindeklas.nl",
		"serializers": ["msgpack"],
		"max_retries": 0
	}],
	realm="rie.667448cb755a12a49504e352",
)

wamp.on_join(main)

if __name__ == "__main__":
	run([wamp])
    


