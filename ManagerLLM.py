import sqlite3
from openai import OpenAI
client = OpenAI()

class fullResponse:
    def __init__(self):
        self.spokenResponse = ""
        self.textResponse = []

def outputDebug(inputText):
    print('\033[95m' + inputText + '\033[0m')

class ManagerLLM:
    def __init__(self, systemPrompt, introductoryText):
        self.systemPrompt = systemPrompt
        self.clientName = ""
        self.introductoryText = introductoryText
        self.clientName = ""
        self.clientPassword = ""
        self.messageLog = [{"role": "system", "content": self.systemPrompt}]
        self.connectionDB = sqlite3.connect('userHistroy.db')
        self.cursorDB = self.connectionDB.cursor()
        self.cursorDB.execute("SELECT * FROM chatSummaries")

        rows = self.cursorDB.fetchall()

        for row in rows:
            print(row)


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
        self.cursorDB.execute("SELECT chats FROM chatSummaries WHERE name = ? AND password = ?", (self.clientName.lower(), self.clientPassword))
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
                (self.clientName.lower(), self.clientPassword, completion.choices[0].message.content)
            )
        else:
            outputDebug("recurring")
            self.cursorDB.execute(
                "UPDATE chatSummaries SET chats = ? WHERE name = ? AND password = ?",
                (completion.choices[0].message.content, self.clientName.lower(), self.clientPassword)
            )
        print(completion.choices[0].message.content)
        self.connectionDB.commit()
        self.connectionDB.close()
        return True

    def convertResponse(self, response):
        fullResponse = fullResponse()
        #extract routines or long lists from response
        fullResponse.spokenResponse = response
        return fullResponse
    
    def outputResponse(self, response):
        print('\033[92m \033[1m' + "FitBot: " + '\033[0m', response)
        #TODO: output response to audio stream

    def isAffirmative(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Your task is to disquintish between affirmative and negative responses. Respond 'true' if the statement confirms something or is an affirming statement and 'false' if it denies something or is a negative statement. Possible cases for true are cases that include 'yes', 'indeed', 'certainly', 'absolutely', 'okay', 'ok', 'correct' or 'of course'. Possible cases for false are cases that include 'no', 'not really', 'unfortunately not', 'mistake' or 'never'. Please provide the correct response to the following user input: " + inputText}
            ]
        )
        outputDebug(completion.choices[0].message.content)
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
        
    def includesPassword(self, inputText):
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "Your task is to disquintish between responses in which the user does or does not provide a password. Respond 'false' there is most likely no password in the input and 'true: [password]' if there is. A positive example could be a single word, particularly when there are one or multiple digits following it. Please provide the correct response to the following user input: " + inputText}
            ]
        )
        if "true" in completion.choices[0].message.content.lower():
            return completion.choices[0].message.content
        else:
            return False

    def mainLoop(self):
        #TODO: Use LLM to determine wether sentence is complete

        #TODO: Use keyword recogniction of NAO to start conversation
        user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
        while user_input.lower() != "hello fitbot":
            user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
        
        self.outputResponse(self.introductoryText)
        user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
        self.addMessageToLog("assistant", "Have we had the pleasure of crossing paths before?")
        self.addMessageToLog("user", user_input)
        if self.isAffirmative(user_input): #returning user
            outputDebug("Returning user")
            includesName = self.includesName(user_input)
            if includesName == False:
                self.outputResponse("Alright, could you tell me your name so I can retrieve the details of our last conversation?")
                user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                includesName = self.includesName(user_input)
                if includesName == False:
                    nameFound = False
                    name = ""
                    while not nameFound:
                        self.outputResponse("I'm sorry, I didn't catch your name. Could you kindly provide your name again?")
                        name = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        self.outputResponse("Thank you! can you confirm your name is " + name + "?")
                        user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        nameFound = self.isAffirmative(user_input)
                    self.clientName = name
                    self.addMessageToLog("user", "My name is" + name)
                else:
                    self.clientName = includesName.split(": ")[1]
            else: 
                self.clientName = includesName.split(": ")[1]
            self.outputResponse("Welcome back, " + self.clientName + "! Could you now tell me your password?")
            password = input('\033[96m \033[1m'+ "User: " + '\033[0m')
            self.outputResponse("Thank you! can you confirm your password is " + password + "?")
            user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
            while not self.isAffirmative(user_input):
                self.outputResponse("I'm sorry, could you provide me your password once again?")
                password = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                self.outputResponse("Thank you! can you confirm your password is " + password + "?")
                user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
            self.clientPassword = password
            self.outputResponse(self.loadConversation())

                
            #TODO:retrieve details from database, provide quick summary of last conversation
            while True:
                user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                response = self.generateAnswer(user_input)
                if '<stop>' in response:
                    response = response.split('<stop>')[0]
                    self.outputResponse(response)
                    self.saveConversation(False)
                    break
                self.outputResponse(response)

        else: #new user
            outputDebug("New user")
            includesName = self.includesName(user_input)
            if includesName == False:
                self.outputResponse("Nice to meet you! Are you okay with sharing your name? It would help me address you more personally throughout our conversation.")
                user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                if self.isAffirmative(user_input):
                    self.permissions = True
                    includesName = self.includesName(user_input)
                    if includesName == False:
                        nameFound = False
                        self.outputResponse("Great! Could you tell me your name?")
                        name = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        self.outputResponse("Thank you! can you confirm your name is " + name + "?")
                        user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        while not self.isAffirmative(user_input):
                            self.outputResponse("I'm sorry. Could you kindly provide your name again?")
                            name = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                            self.outputResponse("Thank you! Can you confirm your name is " + name + "?")
                            user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        self.clientName = name
                    else:
                        self.clientName = includesName.split(": ")[1]
                    self.addMessageToLog("user", "My name is" + self.clientName)
                    self.addMessageToLog("assistant", "Nice to meet you, " + self.clientName + "! How can I help you today?")
                    self.outputResponse("Nice to meet you, " + self.clientName + "! Before we start our conversation, could you please provide a password, so I can reference our conversation next time we meet?")
                    response = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                    includesPassword = self.includesPassword(response)
                    if includesPassword == False:
                        passwordFound = False
                        password = ""
                        while not passwordFound:
                            self.outputResponse("I'm sorry. Could you kindly provide your password again?")
                            password = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                            self.outputResponse("Thank you! can you confirm your password is " + password + "?")
                            user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                            passwordFound = self.isAffirmative(user_input)
                        self.clientPassword = password
                    else:
                        password = includesPassword.split(": ")[1]
                        self.outputResponse("Thank you! Can you confirm your password is " + password + "?")
                        user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        while not self.isAffirmative(user_input):
                            self.outputResponse("I'm sorry. Could you kindly provide your password again?")
                            password = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                            self.outputResponse("Thank you! Can you confirm your password is " + password + "?")
                            user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                        self.clientPassword = password
                    self.outputResponse("Great! I have saved your password. Let's get started! What can I help you with today?")
                else:
                    self.permissions = False
                    self.outputResponse("Thats okay, what can I help you with today?")
            else: 
                self.clientName = includesName.split(": ")[1]
                self.outputResponse(self.loadConversation())
                #self.outputResponse("Nice to meet you, " + self.clientName + "! How can I help you today?")

            while True:
                user_input = input('\033[96m \033[1m'+ "User: " + '\033[0m')
                response = self.generateAnswer(user_input)
                if '<stop>' in response:
                    response = response.split('<stop>')[0]
                    self.outputResponse(response)
                    self.saveConversation(True)
                    break
                self.outputResponse(response)

systemPrompt = "You are a friendly virtual fitness coach, called FitBot, talking to your client. Mention their name if you know this and is seems appropiate. Be sure to keep a professional and well-mannered conversation. Don't answer any off-topic questions. If someone does ask you a question unrelated to fitness, explain that you are unable to answer it and do not provide the answer to the question. If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information. If you  are provding a list of exercises or a routine,  mark the beginning of the list with <list> and the end with </list>. Only mark the list itself, so that it can be extracted. If you have any comments about the routine or about specific exercises, dont include them in the marked area, but put them before or after. Write down the exercises in the following format:  '[exerciseNr][exercise]; [sets]; [reps]\n'. If you do include a <list></list> section in your response, reference to this in your response. If the conversation seems to be reaching its end, ask whether the user/client has any more fitness-related questions or whether you can be of any more assistance, but don't ask this too often through the conversation. If they don't, you can end the conversation with a friendly greeting in which you adress them by their name if you know their name, and insert the keyword '<stop>' at the very end. If you finish with a question, don't end the conversation yet, as the user won't be able to answer your question anymore then."
introductoryText = "Hello! I am FitBot, your robotic virtual fitness coach. I am here to help you with your fitness journey. I can provide you with information about exercises, routines, and general fitness advice. If you have any questions, feel free to ask me. If you want to end our conversation, please say the phrase 'Bye FitBot'. Before we start our conversation, I was wondering if have we had the pleasure of crossing paths before?"
LLM = ManagerLLM(systemPrompt, introductoryText)
LLM.mainLoop()

