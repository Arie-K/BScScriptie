from autobahn.twisted.component import Component, run
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from twisted.internet.task import deferLater
from google.cloud import speech
from google.cloud.speech_v1 import types
from ManagerLLM import ManagerLLM
import time
import queue

sess = None
audioData = queue.Queue()
listening = True
silenceStartTime = None
streamingLimit = 280  # Limit in seconds for each streaming call (to avoid timeout)

systemPrompt = "You are a friendly virtual fitness coach, called FitBot, talking to your client. Mention their name if you know this and is seems appropiate. Be sure to keep a professional and well-mannered conversation. Don't answer any off-topic questions. If someone does ask you a question unrelated to fitness, explain that you are unable to answer it and do not provide the answer to the question. If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information. Please keep the response short and concise, answering the question straight to the point, preferably with at most 1 to 3 senteces, unless you need to elaborate on a particular subject further or are providing a routine, list or enumeration. If you are provding a list of exercises or a (warm-up) routine, mark the beginning of the list with <list> and the end with </list>. Only mark the list itself, so that it can be extracted. If you have any comments about the routine or about specific exercises, dont include them in the marked area, but put them before or after. When referencing the list (for example, when saying 'here is the routine:'), keep in mind that the list will be displayed on a seperate display, so don't use ':', but refer to the display. Write down the exercises in the following format:  '[exerciseNr][exercise]; [sets]; [reps]\n'. If you do include a <list></list> section in your response, reference to this in your response. If the conversation seems to be reaching its end, ask whether the user/client has any more fitness-related questions or whether you can be of any more assistance, but don't ask this too often through the conversation. If they don't, you can end the conversation with a friendly greeting in which you adress them by their name if you know their name, and insert the keyword '<stop>' at the very end. If you finish with a question, don't end the conversation yet, as the user won't be able to answer your question anymore then."
introductoryText = "Hello! I am FitBot, your robotic virtual fitness coach. I am here to help you with your fitness journey. I can provide you with information about exercises, routines, and general fitness advice. Before we start our conversation, I was wondering whether we have had the pleasure of crossing paths before?"
LLM = ManagerLLM(systemPrompt, introductoryText)

def transcribeFrame(frame):
    global audioData
    audioChunk = frame["data"].get("body.head.front", b"")
    audioData.put(audioChunk)
    # print(f"Received audio chunk of size: {len(audio_chunk)}")

def generate_audio_chunks():
    global audioData
    while True:
        if audioData.empty() and LLM.listening:
            if silenceStartTime is None and LLM.nrUnprocessedTranscriptions > 0:
                silenceStartTime = time.time()
            elif silenceStartTime is not None:
                silenceDuration = time.time() - silenceStartTime
                # print(f"Silence duration: {silenceDuration}")
                # print("Silence limit: ", LLM.silenceLimit)
                if silenceDuration > LLM.silenceLimit:
                    print("Silence detected, stopping transcription")
                    LLM.doneTalking = True
                    LLM.listening = False
                    silenceStartTime = None
        else:
            silenceStartTime = None

        # print(LLM.listening)
        # print("Generating audio chunks...", LLM.listening)
        while not audioData.empty():
            chunk = audioData.get() if LLM.listening else audioData.get() * 0
            # print(f"Yielding audio chunk of size: {len(chunk)}")
            yield types.StreamingRecognizeRequest(audio_content=chunk)
        yield types.StreamingRecognizeRequest(audio_content=b"")
            

@inlineCallbacks
def handle_question(session):
    audioData.queue.clear()

    yield session.subscribe(transcribeFrame, "rom.sensor.hearing.stream")
    yield session.call("rom.sensor.hearing.stream")
    # Start the transcription thread
    reactor.callInThread(transcribe_streaming)

    LLM.robotSession = session

    yield LLM.mainLoop()
    print("Stopped main loop")
    

    # while LLM.listening:
    #     yield deferLater(reactor, 0.1, lambda: None)  # Yield control to allow other operations

    yield session.call("rom.sensor.hearing.close")
    print("Stopped listening")

@inlineCallbacks
def transcribe_streaming():
        client = speech.SpeechClient.from_service_account_file("/home/arie/UniLeiden/gcloudkey/scriptiellm-440971c004cf.json")
        speechContexts = [speech.SpeechContext(phrases=["fitbot", "pincode", "pin code", "code", "plan", "lunge", "bulgarian split squat", "PIN", "push", "pull", "legs", "calisthenics", "workout", "routine", "exercise", "gym", "fitness", "strength", "training", "muscle", "body", "weight", "lifting", "squat", "deadlift", "bench press", "barbell", "dumbbell", "kettlebell", "cardio", "calories", "burn", "fat", "protein", "carbs", "diet", "nutrition", "meal", "plan", "rest", "recovery", "sleep", "hydrate", "water", "supplement", "vitamin", "mineral", "protein shake", "pre workout", "post workout", "warm up", "cool down", "stretch", "flexibility", "mobility", "injury", "pain", "soreness", "form", "technique", "spotter", "personal trainer", "coach", "motivation", "inspiration", "goal", "progress", "success", "failure", "discipline", "consistency", "calf", "quadriceps", "hamstring", "glute", "core", "ab", "ab workout", "abs", "obliques", "chest", "back", "shoulder", "trapezius", "traps", "bicep", "tricep", "forearm", "wrist", "thigh", "hip", "waist", "belly", "butt", "arm", "leg", "neck", "head", "heart", "lung", "blood", "vein", "bone", "joint", "tendon", "ligament", "spine", "rib", "nerve", "skin", "sweat", "fat", "metabolism", "hormone", "physical", "health", "infection", "inflammation", "pain", "discomfort", "symptom", "diagnosis", "treatment", "recovery" ] + LLM.registeredNames)]
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=False,
            model="video",
            speech_contexts=speechContexts
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )
        def start_streaming():
            try:
                streamingRequests = generate_audio_chunks()
                responses = client.streaming_recognize(config=streaming_config, requests=streamingRequests)

                print("Starting streaming recognition...")

                startTime = time.time()

                for response in responses:
                    for result in response.results:
                        if result.is_final:
                            transcription = result.alternatives[0].transcript
                            print("Final Transcription: ", transcription)
                            LLM.processTranscription(transcription)
                            if time.time() - startTime > streamingLimit:
                                print("Restarting stream to avoid timeout...")
                                break

            except Exception as e:
                print(f"Error during streaming recognition: {e}")

        while True:
            start_streaming()
            time.sleep(0.3)  # Small delay to avoid rapid restart

@inlineCallbacks
def main(session, details):
    global sess
    sess = session
    yield handle_question(session)
    sess.leave()  # Close connection with the robot

wamp = Component(
    transports=[{
        "url": "ws://wamp.robotsindeklas.nl",
        "serializers": ["msgpack"],
        "max_retries": 0
    }],
    realm="rie.6672aad7755a12a49504d8fc",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
