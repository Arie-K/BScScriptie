import sqlite3
from openai import OpenAI
from twisted.internet.task import deferLater
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks
import re
from autobahn.twisted.util import sleep

client = OpenAI()

def OutputDebug(inputText):
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
        self.silenceLimit = 1.5
        self.registeredNames = []

        self.cursorDB.execute("SELECT name FROM chatSummaries")
        rows = self.cursorDB.fetchall()
        for row in rows:
            self.registeredNames.append(row[0])

    def AddMessageToLog(self, role, content):
        self.messageLog.append({"role": role, "content": content})

    def GenerateAnswer(self, prompt):
        self.AddMessageToLog("user", prompt)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=self.messageLog
        )
        self.AddMessageToLog("assistant", completion.choices[0].message.content)

        return completion.choices[0].message.content
    
    def LoadConversation(self):
        self.cursorDB.execute("SELECT chats FROM chatSummaries WHERE name = ? AND pincode = ?", (self.clientName.lower(), self.clientPincode))
        chatHistory = self.cursorDB.fetchall()
        instructionMessage = (
            "The following is a summary of the last conversation you had with this particular client. Quickly summarize this in your response and catch up with the client."
            "You could ask about their progression or about how they felt about some of the advice you gave them, for example whether they implemented it succesfully."
            "Try to ask a question with makes it clear that you remember your last conversation together."
            "Keep the context of this previous conversation in mind while answering questions during the rest of the conversation."
            "This is the summary of the last conversation: " + chatHistory[0][0]
        )
        self.AddMessageToLog("system", instructionMessage)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=self.messageLog
        )
        return completion.choices[0].message.content

    def SaveConversation(self, new):
        instructionMessage = (
            "Summarize the entire conversation up to this point, including the summary you may have been provided with at the start of the conversation,"
            "using short sententences or keywords. Do this in a way so you could retrieve the most important conversation topics if you were to read this summary later,"
            "in order to give more personalized feedback in future conversation. Especially focus on personal details of the client, not so much on the flow of the conversation."
            "Be sure to include the last conversation in your summary. You do not have to mention every conversational detail that occurred, just the most important things that were discussed."
        )
        self.AddMessageToLog("system", instructionMessage)
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=self.messageLog
        )
        if(new):
            OutputDebug("new")
            self.cursorDB.execute(
                "INSERT INTO chatSummaries VALUES (?, ?, ?)",
                (self.clientName.lower(), self.clientPincode, completion.choices[0].message.content)
            )
        else:
            OutputDebug("recurring")
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
        
    def PinCorrect(self):
        self.cursorDB.execute("SELECT pincode FROM chatSummaries WHERE name = ?", (self.clientName.lower(),))
        pincode = self.cursorDB.fetchall()[0][0]
        if pincode == self.clientPincode:
            OutputDebug("PinCorrect: true")
            return True
        else:
            OutputDebug("PinCorrect: false")
            return False

    def ConvertResponse(self, text):
        list_pattern = re.compile(r'<list>(.*?)</list>', re.DOTALL)
        
        list_match = list_pattern.search(text)
        if list_match:
            list_content = list_match.group(1).strip()
            
            cleaned_text = list_pattern.sub('', text).strip()
            
            exercises = []
            for line in list_content.split('\n'):
                if line.strip():
                    parts = line.split(';')
                    if len(parts) == 3:
                        exercise = parts[0].strip()
                        sets = parts[1].strip()
                        reps = parts[2].strip()
                        exercises.append((exercise, sets, reps))
            
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
            
            self.robotSession.call("ridk.fitbot.SetRoutine", routineHTML)
            
            return cleaned_text
        else:
            return text
        
    def ConvertToPinCode(self, inputString):
        numberMap = {
            "zero": "0", "one": "1", "two": "2", "three": "3",
            "four": "4", "five": "5", "six": "6", "seven": "7",
            "eight": "8", "nine": "9"
        }
        
        parts = inputString.split()
        
        pinCode = []
        
        for part in parts:
            cleanedPart = "".join(filter(str.isalnum, part))
            
            if cleanedPart in numberMap:
                pinCode.append(numberMap[cleanedPart])
            elif cleanedPart.isdigit():
                pinCode.append(cleanedPart)
        
        pinCodeStr = ''.join(pinCode)
        
        if len(pinCodeStr) == 4:
            OutputDebug(pinCodeStr)
            self.clientPincode = pinCodeStr
            return True
        else:
            return False
    
    @inlineCallbacks
    def OutputResponse(self, response):
        response = self.ConvertResponse(response)
        print('\033[92m \033[1m' + "FitBot: " + '\033[0m', response)
        self.listening = False
        try:   
            yield self.robotSession.call("ridk.fitbot.SetStatus", "Speaking", True)
            yield self.robotSession.call("ridk.fitbot.SetResponse", response)
            yield self.robotSession.call("rie.dialogue.say_animated", text=response, lang="en")
            yield self.robotSession.call("ridk.fitbot.SetStatus", "Listening", True)
        except Exception as e:
            print(e)

    def ObtainUserInput(self):
        self.listening = True
        return self._wait_for_transcription()

    def _wait_for_transcription(self):
        d = defer.Deferred()
        self._check_transcription(d)
        return d

    def _check_transcription(self, d):
        if self.transcriptionComplete or self.doneTalking:
            OutputDebug("complete " + str(self.transcriptionComplete) + str(self.doneTalking))
            self.doneTalking = False
            self.listening = False
            self.robotSession.call("ridk.fitbot.SetStatus", "Processing", True)
            userInput = self.transcription
            if userInput.strip() == "":
                userInput = "* silence *"
            self.transcription = ""
            self.transcriptionComplete = False
            self.nrUnprocessedTranscriptions = 0
            d.callback(userInput)
        else:
            if self.listening:
                reactor.callLater(0.1, self._check_transcription, d)

    def IsAffirmative(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Your task is to disquintish between affirmative and negative responses."
                        "Respond 'true' if the statement confirms something or is an affirming statement and 'false' if it denies something or is a negative statement."
                        "Possible cases for true are cases that include 'yes', 'indeed', 'certainly', 'absolutely', 'okay', 'ok', 'correct', 'yeah', 'sure', 'affirmative' or 'of course'."
                        "Possible cases for false are cases that include 'no', 'not really', 'unfortunately not', 'mistake', 'false', 'negative' or 'never'."
                        "Please provide the correct response to the following user input: " + inputText
                    )
                }
            ]
        )
        OutputDebug("affirmative:" + completion.choices[0].message.content)
        if "true" in completion.choices[0].message.content.lower():
            return True
        else:
            return False
        
    def IncludesName(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Your task is to disquintish between responses in which the user does or does not introduce themselves."
                        "Respond 'false' they have not introduced themselves and 'true: [their_name]' if they have."
                        "Possible cases for true could be when the user uses phrases like 'my name is [name]' or 'I'm [name]'."
                        "However, a single word as a response can also be their name, since the user has just been asked to provide their name."
                        "In that case, this also counts as them introducing themselves, so it is a positive/true case and [name] is the single word they responded."
                        "Please provide the correct response to the following user input: " + inputText
                    )
                }
            ]
        )
        if "true" in completion.choices[0].message.content.lower():
            return completion.choices[0].message.content
        else:
            return False
        
    def IncludesPincode(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Your task is to disquintish between responses in which the user does or does not provide a pincode."
                        "Respond 'false' there is most likely no pincode in the input and 'true: [pincode]' if there is."
                        "A positive example could be just the pincode, or an affirmation first, followed by the pincode."
                        "The pincode could either be written as digits (4 7 6) or the digits could be written out (four seven six)."
                        "The length of the pincode is irrelevant. Please provide the correct response to the following user input: " + inputText
                    )
                }
            ]
        )
        if "true" in completion.choices[0].message.content.lower():
            OutputDebug("includesPincode: true")
            return completion.choices[0].message.content
        else:
            OutputDebug("includesPincode: false")
            return False
        
    def IsFinishedSpeaking(self, inputText):
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
        
    def ProcessTranscription(self, transcription):
        self.transcription += " " + transcription
        self.nrUnprocessedTranscriptions += 1
        self.robotSession.call("ridk.fitbot.SetStatus", "Processing", True)
        if self.IsFinishedSpeaking(self.transcription):
            OutputDebug("sentence complete")
            self.transcriptionComplete = True
        elif self.listening:
            self.robotSession.call("ridk.fitbot.SetStatus", "Listening", True)

    @inlineCallbacks
    def UnpersonalizedLoop(self):
        yield sleep(2)

        yield self.robotSession.call("rom.optional.behavior.play", name='BlocklyStand')
        userInput = yield self.ObtainUserInput()
        OutputDebug("userInput: " + userInput)
        while "coaching" not in userInput.lower():
            yield self.robotSession.call("ridk.fitbot.SetStatus", "Listening", True)
            userInput = yield self.ObtainUserInput()
            OutputDebug("userInput: " + userInput)
        
        OutputDebug("keyword found")

        self.AddMessageToLog("assistant", self.introductoryText)
        yield self.OutputResponse(self.introductoryText)

        # Conversation loop using LLM responses
        OutputDebug("start unpersonalized conversation loop")
        while True:
            userInput = yield self.ObtainUserInput()
            response = self.GenerateAnswer(userInput)
            if '<stop>' in response:
                response = response.split('<stop>')[0]
                yield self.OutputResponse(response)
                yield self.OutputResponse("Session over.")
                yield self.robotSession.call("ridk.fitbot.SetStatus", "Offline", False)
                break
            yield self.OutputResponse(response)

    @inlineCallbacks
    def PersonalizedLoop(self):
        OutputDebug("main loop")
        yield sleep(2)

        yield self.robotSession.call("rom.optional.behavior.play", name='BlocklyStand')
    
        userInput = yield self.ObtainUserInput()
        OutputDebug("userInput: " + userInput)
        while "coaching" not in userInput.lower(): #activate coaching wasn't awalys recognized
            yield self.robotSession.call("ridk.fitbot.SetStatus", "Listening", True)
            userInput = yield self.ObtainUserInput()
            OutputDebug("userInput: " + userInput)
        
        OutputDebug("keyword found")

        yield self.OutputResponse(self.introductoryText)
        userInput = yield self.ObtainUserInput()
        self.AddMessageToLog("assistant", "Have we had the pleasure of crossing paths before?")
        self.AddMessageToLog("user", userInput)

        permission = True
        new = False

        # Returning user
        if self.IsAffirmative(userInput):
            OutputDebug("Returning user")
            # Check if name is provided in inital response
            includesName = self.IncludesName(userInput)
            includesPincode = self.IncludesPincode(userInput)
            if not includesName:
                # Ask for name
                yield self.OutputResponse("Alright, could you tell me your name so I can retrieve the details of our last conversation?")
                userInput = yield self.ObtainUserInput()
                includesName = self.IncludesName(userInput)
                # Ask for name again if not provided or not recognized in response
                if not includesName:
                    yield self.OutputResponse("I'm sorry, I didn't catch your name. Could you kindly provide your name again?")
                    name = yield self.ObtainUserInput()
                else:
                    name = includesName.split(": ")[1]
            else: 
                name = includesName.split(": ")[1]
            name = name.strip()
            yield self.OutputResponse("Good to see you again! Can you confirm your name is " + name + "?")
            userInput = yield self.ObtainUserInput()
            # Loop until user confirms name
            while not self.IsAffirmative(userInput):
                yield self.OutputResponse("I'm sorry. Could you kindly provide your name again?")
                name = yield self.ObtainUserInput()
                yield self.OutputResponse("Thank you! Can you confirm your name is " + name + "?")
                userInput = yield self.ObtainUserInput()
            # Name confirmed
            OutputDebug("Name confirmed")
            self.clientName = name.strip()
            # Check for name in database
            nameFound = self.nameFound()
            if not nameFound:
                new = True
                yield self.OutputResponse("I'm sorry, " + self.clientName + ", I can't recollect our previous interaction. Before we start our conversation, could you please provide a 4 digit pincode, so I can reference our conversation next time we meet?")
            self.AddMessageToLog("user", "Yes, my name is " + self.clientName)

            # No pincode provided yet; ask for pincode
            if not includesPincode or not nameFound:
                if nameFound:
                    yield self.OutputResponse("Welcome back, " + self.clientName + "! Could you now tell me your 4 digit pincode?")
                userInput = yield self.ObtainUserInput()
                includesPincode = self.IncludesPincode(userInput)
                # Loop until user provides pincode
                while not includesPincode:
                    yield self.OutputResponse("Could you tell me your 4 digit pincode?")
                    userInput = yield self.ObtainUserInput()
                    includesPincode = self.IncludesPincode(userInput)
            pincode = includesPincode.split(": ")[1]
            # Loop until pincode is valid
            while not self.ConvertToPinCode(pincode):
                yield self.OutputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                pincode = yield self.ObtainUserInput()
            # Confirm pincode
            yield self.OutputResponse("Thank you! Can you confirm your pincode is " + self.clientPincode + "?")
            userInput = yield self.ObtainUserInput()
            # Loop until pincode is confirmed
            while not self.IsAffirmative(userInput):
                yield self.OutputResponse("I'm sorry, could you provide your pincode once again?")
                pincode = yield self.ObtainUserInput()
                while not self.ConvertToPinCode(pincode):
                    yield self.OutputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                    pincode = yield self.ObtainUserInput()
                yield self.OutputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                userInput = yield self.ObtainUserInput()
            # Pincode confirmed
            OutputDebug("pin confirmed")

            # Check for pincode in database, loop until pincode is correct
            if nameFound:
                while not self.PinCorrect():
                    OutputDebug("pin incorrect")
                    yield self.OutputResponse("I'm sorry, the pincode you provided is incorrect. Could you provide your pincode again?")
                    pincode = yield self.ObtainUserInput()
                    # Loop until pincode is valid
                    while not self.ConvertToPinCode(pincode):
                        yield self.OutputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                        pincode = yield self.ObtainUserInput()
                    # Confirm pincode
                    yield self.OutputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                    userInput = yield self.ObtainUserInput()
                    # Loop until pincode is confirmed
                    while not self.IsAffirmative(userInput):
                        yield self.OutputResponse("I'm sorry, could you provide your pincode once again?")
                        pincode = yield self.ObtainUserInput()
                        while not self.ConvertToPinCode(pincode):
                            yield self.OutputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                            pincode = yield self.ObtainUserInput()
                        yield self.OutputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                        userInput = yield self.ObtainUserInput()

            OutputDebug("pin correct")
            # Load conversation and output response
            if nameFound:
                yield self.OutputResponse(self.LoadConversation())
            else:
                yield self.OutputResponse("Great! I have saved your pincode, " + self.clientName + ". Let's get started! What can I help you with today?")

        # New user
        else:
            new = True
            OutputDebug("New user")
            # Check if name is provided in inital response
            includesName = self.IncludesName(userInput)
            # If name is not provided, ask for name
            if not includesName:
                yield self.OutputResponse("Nice to meet you! Are you okay with sharing your name? It would help me address you more personally throughout our conversation.")
                userInput = yield self.ObtainUserInput()
                if not self.IsAffirmative(userInput):
                    permission = False
                    yield self.OutputResponse("Thats okay, what can I help you with today?")
                else:
                    includesName = self.IncludesName(userInput)
                    if includesName == False:
                        yield self.OutputResponse("Great! Could you tell me your name?")
                        userInput = yield self.ObtainUserInput()
                        includesName = self.IncludesName(userInput)
                        # Ask for name again if not provided or not recognized in response
                        if not includesName:
                            yield self.OutputResponse("I'm sorry, I didn't catch your name. Could you kindly provide your name again?")
                            name = yield self.ObtainUserInput()
                        else:
                            name = includesName.split(": ")[1] # includesName() is not reliable enough to use here (since some names are not recognized as names by the model)
                    else:
                        name = includesName.split(": ")[1]
                    yield self.OutputResponse("Thank you! Can you confirm your name is " + name + "?")
            else:
                name = includesName.split(": ")[1]
                yield self.OutputResponse("Nice to meet you! Can you confirm your name is " + name + "?")
            
            # If name is provided, confirm and ask for pincode
            if permission:
                userInput = yield self.ObtainUserInput()
                # Loop until user confirms name
                while not self.IsAffirmative(userInput):
                    yield self.OutputResponse("I'm sorry. Could you kindly provide your name again?")
                    name = yield self.ObtainUserInput()
                    yield self.OutputResponse("Thank you! Can you confirm your name is " + name + "?")
                    userInput = yield self.ObtainUserInput()
                # Name confirmed
                self.clientName = name.strip()
                self.AddMessageToLog("user", "No we have not, my name is" + self.clientName)
                self.AddMessageToLog("assistant", "Nice to meet you, " + self.clientName + "! How can I help you today?") # Pincode does not need to be included in messagelog
                # Ask for pincode
                yield self.OutputResponse("Nice to meet you, " + self.clientName + "! Before we start our conversation, could you please provide a 4 digit pincode, so I can reference our conversation next time we meet?")
                #continue flow here
                userInput = yield self.ObtainUserInput()
                includesPincode = self.IncludesPincode(userInput)
                # Loop until user provides pincode
                while not includesPincode:
                    yield self.OutputResponse("Could you tell me your 4 digit pincode?")
                    userInput = yield self.ObtainUserInput()
                    includesPincode = self.IncludesPincode(userInput)
                pincode = includesPincode.split(": ")[1]
                # Loop until pincode is valid
                while not self.ConvertToPinCode(pincode):
                    yield self.OutputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                    pincode = yield self.ObtainUserInput()
                # Confirm pincode
                yield self.OutputResponse("Thank you! Can you confirm your pincode is " + self.clientPincode + "?")
                userInput = yield self.ObtainUserInput()
                # Loop until pincode is confirmed
                while not self.IsAffirmative(userInput):
                    yield self.OutputResponse("I'm sorry, could you provide your pincode once again?")
                    pincode = yield self.ObtainUserInput()
                    while not self.ConvertToPinCode(pincode):
                        yield self.OutputResponse("Invalid pincode. Please provide a valid 4 digit pincode.")
                        pincode = yield self.ObtainUserInput()
                    yield self.OutputResponse("Thank you! can you confirm your pincode is " + self.clientPincode + "?")
                    userInput = yield self.ObtainUserInput()
                # Pincode confirmed
                yield self.OutputResponse("Great! I have saved your pincode, " + self.clientName + ". Let's get started! What can I help you with today?")

        # Conversation loop using LLM responses
        OutputDebug("start personalized conversation loop")
        while True:
            userInput = yield self.ObtainUserInput()
            response = self.GenerateAnswer(userInput)
            if '<stop>' in response:
                response = response.split('<stop>')[0]
                yield self.OutputResponse(response)
                yield self.OutputResponse("Session over.")
                yield self.robotSession.call("ridk.fitbot.SetStatus", "Offline", False)
                if (new and permission) or (not new and not nameFound):
                    self.SaveConversation(True)
                elif not new and nameFound:
                    self.SaveConversation(False)
                break
            yield self.OutputResponse(response)
            
