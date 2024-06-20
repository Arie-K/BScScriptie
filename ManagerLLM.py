import sqlite3
from openai import OpenAI
from twisted.internet.task import deferLater
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks
import re
import time

client = OpenAI()

def outputDebug(inputText):
    print('\033[95m' + inputText + '\033[0m')

class ManagerLLM:
    def __init__(self, systemPrompt, introductoryText):
        self.systemPrompt = systemPrompt
        self.clientName = ""
        self.introductoryText = introductoryText
        self.clientName = ""
        self.clientPincode = ""
        self.messageLog = [{"role": "system", "content": self.systemPrompt}]
        self.connectionDB = sqlite3.connect('userHistroy.db')
        self.cursorDB = self.connectionDB.cursor()
        self.cursorDB.execute("SELECT * FROM chatSummaries")
        self.listening = True
        self.transcription = ""
        self.transcriptionComplete = False
        self.nrUnprocessedTranscriptions = 0
        self.robotSession = None
        self.doneTalking = False
        self.silenceLimit = 2.5
        self.registeredNames = []
        self.delayStartTime = 0
        self.is_finalTime = 0
        self.isFinishedSpeakingTime = 0

        self.cursorDB.execute("SELECT name FROM chatSummaries")
        rows = self.cursorDB.fetchall()
        for row in rows:
            self.registeredNames.append(row[0])

    def addMessageToLog(self, role, content):
        self.messageLog.append({"role": role, "content": content})

    def generateAnswer(self, prompt):
        self.addMessageToLog("user", prompt)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=self.messageLog
        )
        self.addMessageToLog("assistant", completion.choices[0].message.content)

        return completion.choices[0].message.content
    
    def loadConversation(self):
        self.cursorDB.execute("SELECT chats FROM chatSummaries WHERE name = ? AND pincode = ?", (self.clientName.lower(), self.clientPincode))
        chatHistory = self.cursorDB.fetchall()
        print(chatHistory)
        self.addMessageToLog("system", "The following is a summary of the last conversation you had with this particular client. Quickly summarize this in your response and catch up with the client. You could ask about their progression or about how they felt about some of the advice you gave them, for example whether they implemented it succesfully. Try to ask a question with makes it clear that you remember your last conversation together. Keep the context of this previous conversation in mind while answering questions during the rest of the conversation. This is the summary of the last conversation: " + chatHistory[0][0])
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=self.messageLog
        )
        return completion.choices[0].message.content

    def saveConversation(self, new):
        self.addMessageToLog("system", "Summarize the entire conversation up to this point, including the summary you may have been provided with at the start of the conversation, using short sententences or keywords. Do this in a way so you could retrieve the most important conversation topics if you were to read this summary later, in order to give more personalized feedback in future conversation. Especially focus on personal details of the client, not so much on the flow of the conversation. Be sure to include the last conversation in your summary. You do not have to mention every conversational detail that occurred, just the most important things that were discussed.")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=self.messageLog
        )
        if(new):
            outputDebug("new")
            self.cursorDB.execute(
                "INSERT INTO chatSummaries VALUES (?, ?, ?)",
                (self.clientName.lower(), self.clientPincode, completion.choices[0].message.content)
            )
        else:
            outputDebug("recurring")
            self.cursorDB.execute(
                "UPDATE chatSummaries SET chats = ? WHERE name = ? AND pincode = ?",
                (completion.choices[0].message.content, self.clientName.lower(), self.clientPincode)
            )
        print(completion.choices[0].message.content)
        self.connectionDB.commit()
        self.connectionDB.close()
        return True
    
    def nameFound(self):
        if self.clientName.lower() in self.registeredNames:
            return True
        else:
            return False
        
    def pinCorrect(self):
        self.cursorDB.execute("SELECT pincode FROM chatSummaries WHERE name = ?", (self.clientName.lower(),))
        pincode = self.cursorDB.fetchall()[0][0]
        if pincode == self.clientPincode:
            outputDebug("pinCorrect: true")
            return True
        else:
            outputDebug("pinCorrect: false")
            return False

    def convertResponse(self, text):
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
            
            self.robotSession.call("ridk.fitbot.setRoutine", routineHTML)

            self.silenceLimit = 10.0
            
            return cleaned_text
        else:
            return text
        
    def convertToPinCode(self, inputString):
        numberMap = {
            "zero": "0", "one": "1", "two": "2", "three": "3",
            "four": "4", "five": "5", "six": "6", "seven": "7",
            "eight": "8", "nine": "9"
        }
        
        # Split the input string by spaces
        parts = inputString.split()
        
        # List to hold the PIN code digits
        pinCode = []
        
        # Iterate over each part
        for part in parts:
            # Remove any non-alphanumeric characters
            cleanedPart = "".join(filter(str.isalnum, part))
            
            # Convert written numbers to digits if present in the map
            if cleanedPart in numberMap:
                pinCode.append(numberMap[cleanedPart])
            elif cleanedPart.isdigit():
                pinCode.append(cleanedPart)
        
       # Join the PIN code digits
        pinCodeStr = ''.join(pinCode)
        
        # Check if the PIN code is exactly 4 digits
        if len(pinCodeStr) == 4:
            outputDebug(pinCodeStr)
            self.clientPincode = pinCodeStr  # Set the password variable
            return True
        else:
            return False
    
    @inlineCallbacks
    def outputResponse(self, response):
        if self.silenceLimit == 10.0:
            self.silenceLimit = 2.0
        response = self.convertResponse(response)
        print('\033[92m \033[1m' + "FitBot: " + '\033[0m', response)
        try:   
            yield self.robotSession.call("ridk.fitbot.setStatus", "Speaking", False)
            yield self.robotSession.call("ridk.fitbot.setResponse", response)
            yield self.robotSession.call("rie.dialogue.say", text=response, lang="en")
            yield self.robotSession.call("ridk.fitbot.setStatus", "Listening", True)
        except Exception as e:
            print(e)

    def obtainUserInput(self):
        self.listening = True
        return self._wait_for_transcription()

    def _wait_for_transcription(self):
        d = defer.Deferred()
        self._check_transcription(d)
        return d

    def _check_transcription(self, d):
        if self.transcriptionComplete or self.doneTalking:
            outputDebug("complete " + str(self.transcriptionComplete) + str(self.doneTalking))
            self.listening = False
            userInput = self.transcription
            if userInput.strip() == "":
                userInput = "* silence *"
            self.transcription = ""
            self.transcriptionComplete = False
            self.doneTalking = False
            self.nrUnprocessedTranscriptions = 0
            d.callback(userInput)
        else:
            # print("not complete")
            reactor.callLater(0.1, self._check_transcription, d)

    def isAffirmative(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Your task is to disquintish between affirmative and negative responses. Respond 'true' if the statement confirms something or is an affirming statement and 'false' if it denies something or is a negative statement. Possible cases for true are cases that include 'yes', 'indeed', 'certainly', 'absolutely', 'okay', 'ok', 'correct', 'yeah', 'sure', 'affirmative' or 'of course'. Possible cases for false are cases that include 'no', 'not really', 'unfortunately not', 'mistake', 'false', 'negative' or 'never'. Please provide the correct response to the following user input: " + inputText}
            ]
        )
        outputDebug("affirmative:" + completion.choices[0].message.content)
        if "true" in completion.choices[0].message.content.lower():
            return True
        else:
            return False
        
    def includesName(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Your task is to disquintish between responses in which the user does or does not introduce themselves. Respond 'false' they have not introduced themselves and 'true: [their_name]' if they have. Possible cases for true could be when the user uses phrases like 'my name is [name]' or 'I'm [name]'. However, a single word as a response can also be their name, since the user has just been asked to provide their name. In that case, this also counts as them introducing themselves, so it is a positive/true case and [name] is the single word they responded. Please provide the correct response to the following user input: " + inputText}
            ]
        )
        if "true" in completion.choices[0].message.content.lower():
            return completion.choices[0].message.content
        else:
            return False
        
    def includesPincode(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Your task is to disquintish between responses in which the user does or does not provide a pincode. Respond 'false' there is most likely no pincode in the input and 'true: [pincode]' if there is. A positive example could be just the pincode, or an affirmation first, followed by the pincode. The pincode could either be written as digits (4 7 6) or the digits could be written out (four seven six). The length of the pincode is irrelevant. Please provide the correct response to the following user input: " + inputText}
            ]
        )
        if "true" in completion.choices[0].message.content.lower():
            outputDebug("includesPincode: true")
            return completion.choices[0].message.content
        else:
            outputDebug("includesPincode: false")
            return False
        
    def isFinishedSpeaking(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a virtual assistant talking to a user."
                        "You will receive an unpunctuated transcription of what the user has said. "
                        "This transcription can be a complete sentence or just a fragment of it. "
                        "Your task is to determine if the user has likely finished speaking the current sentence. "
                        "If the sentence seems complete, or complete enough for you to interpret it and respond with something useful, return 'True'. "
                        "However, if the sentence appears incomplete, cut off, or likely to be extended in the next part, return 'False'. "
                        "Only respond with 'True' or 'False', nothing else. "
                        "Additionally, you will receive a parameter indicating the number of consecutive transcriptions deemed unfinished so far. "
                        "If this number is high, it increases the likelihood that the current transcription is complete. "
                        "The number of consecutive unfinished transcriptions is: " + str(self.nrUnprocessedTranscriptions) + ". "
                        "If you are unsure, favor True over False. If you feel like there could be a continuation, but the statement so far could also be interpeted as a complete sence, return True."
                        "Based on this context, please determine whether the following user input is a complete sentence or not: " + inputText
                    )
                }
            ]
        )
        print(completion.choices[0].message.content)
        return "true" in completion.choices[0].message.content.lower()
        
    def processTranscription(self, transcription):
        self.transcription += " " + transcription
        self.nrUnprocessedTranscriptions += 1
        if self.isFinishedSpeaking(self.transcription):
            outputDebug("sentence complete")
        self.isFinishedSpeakingTime = time.time()-self.delayStartTime - self.is_finalTime
        self.robotSession.call("ridk.fitbot.setStatus", "Processing", True)
        self.transcriptionComplete = True

    @inlineCallbacks
    def testLoop(self):
        #TODO: check where delay is largest and try to reduce it
        yield self.outputResponse("This is a test message")
        self.delayStartTime = time.time()
        userInput = yield self.obtainUserInput()
        print("test")
        userInputReturnedTime = time.time()-self.delayStartTime-self.is_finalTime
        response = yield self.generateAnswer(userInput)
        responseGeneratedTime = time.time()-self.delayStartTime-userInputReturnedTime
        yield self.outputResponse(response)
        responseSpokenTime = time.time()-self.delayStartTime-responseGeneratedTime
        print("is_finalTime: " + str(self.is_finalTime))
        print("isFinishedSpeakingTime: " + str(self.isFinishedSpeakingTime))
        print("userInputReturnedTime: " + str(userInputReturnedTime))
        print("responseGeneratedTime: " + str(responseGeneratedTime))
        print("responseSpokenTime: " + str(responseSpokenTime))

    @inlineCallbacks
    def mainLoop(self):
        outputDebug("main loop")

        yield self.robotSession.call("rom.optional.behavior.play", name='BlocklyCrouch')
    
        userInput = yield self.obtainUserInput()
        outputDebug("userInput: " + userInput)
        while "begin session" not in userInput.lower():
            userInput = yield self.obtainUserInput()
            outputDebug("userInput: " + userInput)
        
        outputDebug("keyword found")

        # yield self.outputResponse(self.introductoryText)
        yield self.outputResponse("Have we had the pleasure of crossing paths before?")
        userInput = yield self.obtainUserInput()
        self.addMessageToLog("assistant", "Have we had the pleasure of crossing paths before?")
        self.addMessageToLog("user", userInput)

        permission = True

        # Returning user
        if self.isAffirmative(userInput):
            outputDebug("Returning user")
            # Check if name is provided in inital response
            includesName = self.includesName(userInput)
            includesPincode = self.includesPincode(userInput)
            if not includesName:
                # Ask for name
                yield self.outputResponse("Alright, could you tell me your name so I can retrieve the details of our last conversation?")
                userInput = yield self.obtainUserInput()
                includesName = self.includesName(userInput)
                # Ask for name again if not provided or not recognized in response
                if not includesName:
                    yield self.outputResponse("I'm sorry, I didn't catch your name. Could you kindly provide your name again?")
                    name = yield self.obtainUserInput()
                else:
                    name = includesName.split(": ")[1]
            else: 
                name = includesName.split(": ")[1]
            name = name.strip()
            yield self.outputResponse("Good to see you again! Can you confirm your name is " + name + "?")
            userInput = yield self.obtainUserInput()
            # Loop until user confirms name
            while not self.isAffirmative(userInput):
                yield self.outputResponse("I'm sorry. Could you kindly provide your name again?")
                name = yield self.obtainUserInput()
                yield self.outputResponse("Thank you! Can you confirm your name is " + name + "?")
                userInput = yield self.obtainUserInput()
            # Name confirmed
            outputDebug("Name confirmed")
            self.clientName = name.strip()
            # Check for name in database
            nameFound = self.nameFound()
            if not nameFound:
                yield self.outputResponse("I'm sorry, " + self.clientName + ", I can't recollect our previous interaction. Before we start our conversation, could you please provide a 4 digit pincode, so I can reference our conversation next time we meet?")
            self.addMessageToLog("user", "Yes, my name is " + self.clientName)

            # No pincode provided yet; ask for pincode
            if not includesPincode or not nameFound:
                if nameFound:
                    yield self.outputResponse("Welcome back, " + self.clientName + "! Could you now tell me your 4 digit pincode?")
                userInput = yield self.obtainUserInput()
                includesPincode = self.includesPincode(userInput)
                # Loop until user provides pincode
                while not includesPincode:
                    yield self.outputResponse("Could you tell me your 4 digit pincode?")
                    userInput = yield self.obtainUserInput()
                    includesPincode = self.includesPincode(userInput)
            pincode = includesPincode.split(": ")[1]
            # Loop until pincode is valid
            while not self.convertToPinCode(pincode):
                yield self.outputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                pincode = yield self.obtainUserInput()
            # Confirm pincode
            yield self.outputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
            userInput = yield self.obtainUserInput()
            # Loop until pincode is confirmed
            while not self.isAffirmative(userInput):
                yield self.outputResponse("I'm sorry, could you provide your pincode once again?")
                pincode = yield self.obtainUserInput()
                while not self.convertToPinCode(pincode):
                    yield self.outputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                    pincode = yield self.obtainUserInput()
                yield self.outputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                userInput = yield self.obtainUserInput()
            # Pincode confirmed
            outputDebug("pin confirmed")

            # Check for pincode in database, loop until pincode is correct
            if nameFound:
                while not self.pinCorrect():
                    outputDebug("pin incorrect")
                    yield self.outputResponse("I'm sorry, the pincode you provided is incorrect. Could you provide your pincode again?")
                    pincode = yield self.obtainUserInput()
                    # Loop until pincode is valid
                    while not self.convertToPinCode(pincode):
                        yield self.outputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                        pincode = yield self.obtainUserInput()
                    # Confirm pincode
                    yield self.outputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                    userInput = yield self.obtainUserInput()
                    # Loop until pincode is confirmed
                    while not self.isAffirmative(userInput):
                        yield self.outputResponse("I'm sorry, could you provide your pincode once again?")
                        pincode = yield self.obtainUserInput()
                        while not self.convertToPinCode(pincode):
                            yield self.outputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                            pincode = yield self.obtainUserInput()
                        yield self.outputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                        userInput = yield self.obtainUserInput()

            outputDebug("pin correct")
            # Load conversation and output response
            if nameFound:
                yield self.outputResponse(self.loadConversation())
            else:
                yield self.outputResponse("Great! I have saved your pincode, " + self.clientName + ". Let's get started! What can I help you with today?")

        # New user
        else:
            outputDebug("New user")
            # Check if name is provided in inital response
            includesName = self.includesName(userInput)
            # If name is not provided, ask for name
            if not includesName:
                yield self.outputResponse("Nice to meet you! Are you okay with sharing your name? It would help me address you more personally throughout our conversation.")
                userInput = yield self.obtainUserInput()
                if not self.isAffirmative(userInput):
                    permission = False
                    yield self.outputResponse("Thats okay, what can I help you with today?")
                else:
                    includesName = self.includesName(userInput) # TODO: maybe run paralell with isAffirmative? (only if delay is too long)
                    if includesName == False:
                        yield self.outputResponse("Great! Could you tell me your name?")
                        name = yield self.obtainUserInput() # includesName() is not reliable enough to use here (since some names are not recognized as names by the model)
                    else:
                        name = includesName.split(": ")[1]
                    yield self.outputResponse("Thank you! Can you confirm your name is " + name + "?")
            else:
                name = includesName.split(": ")[1]
                yield self.outputResponse("Nice to meet you! Can you confirm your name is " + name + "?")
            
            # If name is provided, confirm and ask for pincode
            if permission:
                userInput = yield self.obtainUserInput()
                # Loop until user confirms name
                while not self.isAffirmative(userInput):
                    yield self.outputResponse("I'm sorry. Could you kindly provide your name again?")
                    name = yield self.obtainUserInput()
                    yield self.outputResponse("Thank you! Can you confirm your name is " + name + "?")
                    userInput = yield self.obtainUserInput()
                # Name confirmed
                self.clientName = name.strip()
                self.addMessageToLog("user", "No we have not, my name is" + self.clientName)
                self.addMessageToLog("assistant", "Nice to meet you, " + self.clientName + "! How can I help you today?") # Pincode does not need to be included in messagelog
                # Ask for pincode
                yield self.outputResponse("Nice to meet you, " + self.clientName + "! Before we start our conversation, could you please provide a 4 digit pincode, so I can reference our conversation next time we meet?")
                #continue flow here
                userInput = yield self.obtainUserInput()
                includesPincode = self.includesPincode(userInput)
                # Loop until user provides pincode
                while not includesPincode:
                    yield self.outputResponse("Could you tell me your 4 digit pincode?")
                    userInput = yield self.obtainUserInput()
                    includesPincode = self.includesPincode(userInput)
                pincode = includesPincode.split(": ")[1]
                # Loop until pincode is valid
                while not self.convertToPinCode(pincode):
                    yield self.outputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                    pincode = yield self.obtainUserInput()
                # Confirm pincode
                yield self.outputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                userInput = yield self.obtainUserInput()
                # Loop until pincode is confirmed
                while not self.isAffirmative(userInput):
                    yield self.outputResponse("I'm sorry, could you provide your pincode once again?")
                    pincode = yield self.obtainUserInput()
                    while not self.convertToPinCode(pincode):
                        yield self.outputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                        pincode = yield self.obtainUserInput()
                    yield self.outputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                    userInput = yield self.obtainUserInput()
                # Pincode confirmed
                yield self.outputResponse("Great! I have saved your pincode, " + self.clientName + ". Let's get started! What can I help you with today?")

        # Conversation loop using LLM responses
        outputDebug("start conversation loop")
        while True:
            userInput = yield self.obtainUserInput()
            response = self.generateAnswer(userInput)
            if '<stop>' in response:
                response = response.split('<stop>')[0]
                yield self.outputResponse(response)
                if permission:
                    self.saveConversation(True)
                yield self.outputResponse("Session over.")
                break
            yield self.outputResponse(response)
            
