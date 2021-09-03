import asyncio
import copy
import os
import sys
import threading
import time
import discord
from pynput.keyboard import Controller, Key, KeyCode, Listener
import pyautogui
import cv2
import pytesseract

#Configuration variables
game_name = ""   #Game name
bot_name = "[Zxn100]"   #Bot's in game name
token = ""   #Token for the bot Zxn100 from Discord
guild_id =    #Authorized server's ID
channel_id =   #Authorized channel's ID
emergency_code = "GNZ!" #Emergency code to turn off the program remotely
app_chat_format = "/g [{user}] : {text}"    #Format of chat to be sent to the application, replaces {user} with real user and {text} with real text later
app_chat_condition = ['[',']',':']  #Requirements for chat to be considered a chat, must have these characters included in chat

cycle_delay = 0.1   #Seconds needed for the program to check if there's new texts to type
keyboard_delay = 0.05   #Seconds needed for a key to be typed

image_path = "chat.png" #Screenshot image's path on disk
previous_image_path = "old_chat.png" #Screenshot image's path on disk
pytesseract.pytesseract.tesseract_cmd = 'C:\Program Files\Tesseract-OCR\Tesseract.exe'  #Tesseract.exe's location on the computer

image_color_tolerance = 1000    #Each color's tolerance, used to tolerate more images to be considered the same

def manual_sql_parse(text): #Function that parses a text to prevent dangerous characters for some programs
    text = text.replace("'"," ")    #Removes ' from text to prevent possible sql injection
    text = text.replace('"'," ")    #Removes " from text to prevent possible sql injection
    text = text.replace('--',"  ")  #Removes -- from text to prevent sql commenting
    text = text.replace(';'," ")    #Removes ; from text
    return text #Returns parsed text

message_queue = []  #Queue filled with texts to be typed, the function keyboard_type() will check this list's 0th index for new messages
pynput_char_length = -1 #Stores the length of a chat that will be typed, when not in use stores the value -1, needed to prevent the key enter to be typed when program's typing
pynput_char_counter = -1    #Stores the current index processed of a chat that is being typed, when not in use stores the value -1, needed for program to be able to check if a key inputted is the same as in the chat's index
pynput_enter_counter = -1   #Stores the number of enter presses left available for a chat
isChecking = False    #Boolean that stores the status of whether a checking process is going on

keyboard = Controller() #Declares keyboard to be controlled by the pynput controller

def checked_press(key): #Procedure to press and release a key
    global isChecking
    isChecking = True #Announce checking process started
    keyboard.press(key) #Presses a key, triggers the pynput keyboard listener
    keyboard.release(key)   #Releases that key
    time.sleep(keyboard_delay)  #Delays a bit to mimic human typing
    while(isChecking):  #Checks whether the checking process is already finished
        time.sleep(cycle_delay)  #Delays more

def checked_type(key):  #Procedure to type a specific character
    global isChecking
    isChecking = True #Announce checking process started
    keyboard.type(key)  #Types a specific character, triggers the pynput keyboard listener
    time.sleep(keyboard_delay)  #Delays a bit to mimic human typing
    while(isChecking):  #Checks whether the checking process is already finished
        time.sleep(cycle_delay) #Delays more

def keyboard_type():    #Procedure that will mainly functions to type the chat stored in the message_queue
    global message_queue, pynput_char_counter, pynput_char_length, pynput_enter_counter
    while True:   #Loops the program to continuously checks for a chat in index 0 of the array message_queue
        if len(message_queue)<1:    #Checks if the at least the queue's first index is not empty
            time.sleep(cycle_delay) #Delays the program before checking again
        else:   #Case when a queue is not empty
            pynput_char_counter = 0 #Sets the counter to 0 from -1
            pynput_char_length = len(message_queue[0])  #Sets the integer to store the length of the string
            pynput_enter_counter = 2    #Sets the number of enters left to 2, to open and close chat window
            checked_press(Key.enter)    #Presses enter key
            for c in message_queue[0]:  #Loops through every char in the 0th index of the queue
                checked_type(c)     #Presses specific key for the chat
            checked_press(Key.enter)    #Presses enter key
            message_queue.pop(0)    #Removes the 0th index of the queue, shifting the 1st index to the 0th index if there is
            pynput_char_counter = -1    #Resets the counter to -1
            pynput_char_length = -1 #Resets the length to -1
            pynput_enter_counter = -1   #Resets the counter to -1  

def keyboard_onpress(key):  #Listener to detect of there's any key being pressed that may result inappropriate behavior, listener will turn off the program when such event is detected
    global isChecking, pynput_char_counter, pynput_enter_counter
    if key==Key.enter and pynput_char_counter==0 and pynput_enter_counter<2:    #Checks if double enter key is pressed at the beginning of the chat
        os._exit(0) #Turns off the program
    if key==Key.enter and not pynput_char_counter==0 and not pynput_char_counter==pynput_char_length and pynput_enter_counter<=0:   #Checks if the key enter is pressed on other cases other than at start and end of each message
        os._exit(0) #Turns off the program
    else:   #Case when the enter key usage is correct
        pynput_enter_counter = pynput_enter_counter-1   #Reduces enter counter by 1
    if pynput_char_counter<0 or key==Key.esc: #Checks if any key is being pressed when no chat is to be typed or when the escape key is pressed
        os._exit(0) #Turns off the program
    if not key==Key.enter and pynput_char_counter>=0: #Checks if there is indeed a text to be typed and the key inputted is not an enter key
        if not key==KeyCode.from_char(message_queue[0][pynput_char_counter]) and not (key==Key.space and message_queue[0][pynput_char_counter]==' '):   #Checks if an index of a string is the same as the key inputted
            os._exit(0) #Turns off the program
        else:   #Case when the key to be typed is correct
            pynput_char_counter = pynput_char_counter+1 #Adds the counter
    isChecking = False    #Changes checking status to false, allowing keyboard typing process to continue

def keyboard_listen():  #Keyboard listener's procedure
    with Listener(on_press=keyboard_onpress) as listener:   #Hooks the function keyboard_onpress to the pynput's keyboard listener when any key is pressed
        listener.join() #Iterates the listener process

client = discord.Client()   #Declares the discord client

previous_extracted_string = ""  #Stores the oldest text extracted from screenshot
previous_extracted_chat = []    #Stores the broken down texts from previous_extracted_string

discord_queue = []  #Stores the messages need to be sent to discord

async def send_discord():    #Procedure that sends message to Discord
    global discord_queue
    while True: #Loops forever
        if len(discord_queue)>0:    #Checks if the queue has at least 1 item
            channel = client.get_channel(channel_id)    #Gets the authorized channel's access
            await channel.send(discord_queue[0]) #Sends message
            discord_queue.pop(0)    #Removes sent message
        else:   #When no item is in the list
            await asyncio.sleep(cycle_delay)    #Delays the procedure before looping

def is_chat_duplicate(chat1, chat2):  #Procedure to check if chat1 or chat2 have the same contents included, it's ok for a chat to have more, however the first chats must be the same
    if not len(chat1) == len(chat2):    #Checks if arrays don't have the same length
        return False    #Marks the chat as unique
    for i in range(len(chat1)): #Iterates through the indexes
        if not str(chat1[i].lower().replace(' ',''))==str(chat2[i].lower().replace(' ','')):  #Checks if the items aren't the same
            return False    #Marks the chat as unique
    return True   #Marks the chat as duplicate

def is_chat_overlapping(chat1, chat2):  #Procedure to check if chat1 or chat2 have the same contents included, it's ok for a chat to have more, however the first chats must be the same
    limit = len(chat1)  #Takes the array length of chat1
    if limit>len(chat2):    #Checks if char2 is longer than chat1
        limit=len(chat2)    #Stores the minimum length between chat1 and chat2
    for i in range(limit):  #Checks the first number of limit chat
        if not str(chat1[i].lower().replace(' ',''))==str(chat2[i].lower().replace(' ','')):  #Checks if chat1 and chat2 don't have the same content
            return False  #Returns false
    return True   #Returns true

def chat_parse(text):   #A function that seperates an extracted string to their respective sentences
    sentences = text.split("\n")    #Splits a text by new line character set
    for i in range(len(sentences)-1,0,-1):  #Loops through the sentences in descending order
        if str(bot_name.lower()) == str(sentences[i][0:len(bot_name)].lower()):   #Checks if a chat has the same header as the bot's name
            sentences.pop(i)    #Removes bot's chat
        elif len(str(sentences[i]))<1:   #Checks if chat is empty
            sentences.pop(i)    #Removes empty chat
        else:   #Case when chat isn't filtered
            for c in app_chat_condition:    #Loops throught the array of characters that should be in a chat
                if not c in str(sentences[i]):   #Checks if said string/character is not in the sentence
                    sentences.pop(i)    #Removes sentence that doesn't fulfill said condition
                    break   #Breaks through the loop
    return sentences    #Returns the broken down form of the text

def generate_chat(extracted_string):    #Procedure mainly to check and send messages to discord
    global discord_queue, previous_extracted_string, previous_extracted_chat
    if not extracted_string == previous_extracted_string:   #Checks if the parameter is the same as the last time this procedure is called
        extracted_chat = chat_parse(extracted_string)   #Breaks down the text into array of strings
        chat_archive = copy.deepcopy(extracted_chat)    #Stores the unsullied extracted_chat to later replace previous_extracted_chat
        if not is_chat_duplicate(previous_extracted_chat,extracted_chat):   #Checks if every chat is not the same with previous chat
            if len(extracted_chat)>0:   #Checks if there's a new text
                if len(previous_extracted_chat)>0:  #Checks if there's old chats
                    while not is_chat_overlapping(previous_extracted_chat, extracted_chat): #Loops while the chat has different first chats, when it's done, the older chats can be used to remove first few chats from newer chats, filtering the messages to send
                        if(len(previous_extracted_chat)>0):  #Checks if the old chat have at least 1 chat
                            previous_extracted_chat.pop(0)  #Removes the first chat in the older array
                    for i in range(len(previous_extracted_chat)):   #Checks the older array for messages left
                        if(len(extracted_chat)>0):  #Checks if the new chat have at least 1 chat
                            extracted_chat.pop(0)   #Removes the first index of the newer array, because it has the same content with the older chat
                for c in extracted_chat:    #Loops through the filtered newer chat
                    discord_queue.append(c) #Adds the message to discord queue
            previous_extracted_string = extracted_string    #Replaces the older parameter with the newer parameter to filter next chats
            previous_extracted_chat = copy.deepcopy(chat_archive)  #Replaces the older chats with the newer chats to filter next chats
            os.remove(previous_image_path)  #Deletes old image
            os.rename(image_path, previous_image_path)  #Renames new image to old image

def image_extraction(): #Text recognition module
    im = cv2.imread(image_path, cv2.IMREAD_COLOR)   #Reads the image from the screenshot
    im = cv2.bitwise_not(im) #Inverts the color of image since the image used has black background and white text
    
    config = ('-l eng --oem 1 --psm 3') #Tesseract's configuration
    extracted_string = pytesseract.image_to_string(im, config=config)   #Runs Tesseract OCR, getting the strings from the image
    extracted_string = manual_sql_parse(extracted_string)   #Parses the extracted text
    if emergency_code in extracted_string:  #Checks if a message's content is the same as a dedicated text for remote turn off, doesn't matter from where the source is
        os._exit(0) #Turns off the program
        
    generate_chat(extracted_string) #Processes the extracted string

#Screenshot's dimensional properties
x = -1 #Top-left of screenshot's X coordinate
y = -1 #Top-left of screenshot's Y coordinate
w = -1 #Width of screenshot
h = -1 #Height of screenshot's Y coordinate

def is_image_similar(old_path, new_path):   #Function that checks if an image is similar enough to another image
     if os.path.isfile(old_path):   #Checks if file exists
            new_image = cv2.imread(new_path)    #Reads new image
            old_image = cv2.imread(old_path)    #Reads old image
            if old_image.shape == new_image.shape:  #Checks both images' shapes
                difference = cv2.subtract(old_image, new_image) #Calculate color differences between images
                b, g, r = cv2.split(difference) #Splits the result
                if cv2.countNonZero(b) < image_color_tolerance and cv2.countNonZero(g) < image_color_tolerance and cv2.countNonZero(r) < image_color_tolerance: #Checks if difference is similar enough
                    return True #Marks image as duplicate
                else:   #When color is not the same
                    return False    #Marks image as unique
            else:   #When images' shape is different
                return False    #Marks image as unique
     return False   #Marks image as unique when there's no image to compare to

def image_capture():    #Screenshot procedure
    while True: #Loops forever
        image = pyautogui.screenshot(region=(x,y,w,h))  #Screenshots the monitor from top-left to as much as configured width and height
        image.save(image_path)  #Saves the image to disk on the configured path
        if not is_image_similar(previous_image_path, image_path):   #Checks if image is similar enough for the extraction process to be redundant
            image_extraction()  #Calls for the text extraction process
        time.sleep(cycle_delay) #Delay before the procedure's thread is run over again

@client.event
async def on_ready():   #Function that runs when the program is ready
    thread_keyboard_typing = threading.Thread(target = keyboard_type)   #Declares the thread for the keyboard typing process
    thread_keyboard_typing.start()  #Starts the typing bot thread

    thread_keyboard_listening = threading.Thread(target = keyboard_listen)  #Declares the thread for the keyboard listening process
    thread_keyboard_listening.start()   #Starts the listening bot thread

    thread_image_capture = threading.Thread(target = image_capture) #Declares the thread for the image capturing process
    thread_image_capture.start()    #Starts the image capturing thread
    
    asyncio.run_coroutine_threadsafe(send_discord(),asyncio.get_event_loop())    #Sends message to Discord through async procedure

    channel = client.get_channel(channel_id)    #Gets the authorized channel's access
    await channel.send("Zxn100 has woken up!")  #Sends chat announcing bot is live
    await client.change_presence(activity=discord.Game(name=game_name)) #Changes bot status to playing a game which is configured on the code above
    print("Zxn100 has woken up!")   #Prints text when bot is ready on the console
    print("Pressing any key will stop the script! Please use mouse instead to navigate your computer.") #Warning for user
    
@client.event
async def on_message(message):  #Function that runs when a new message from Discord is detecteds
    text = manual_sql_parse(str(message.content))    #Gets the parsed value of the chat
    if emergency_code in text:  #Checks if a message's content is the same as a dedicated text for remote turn off, doesn't matter from where the source is
        os._exit(0) #Turns off the program

    user = manual_sql_parse(str(message.author))   #Gets the parsed value of the chat's sender
    if user ==  manual_sql_parse(str(client.user)):   #Checks if the message came from the bot
        return  #Exits the function nothing to prevent program to respond to chats from itself
    if  manual_sql_parse(str(message.channel.id))==manual_sql_parse(str(channel_id)): #Checks if the channel id is authorized
        chat = app_chat_format.format(user=user,text=text)   #Formats and adds header to the chat to a single text
        
        global message_queue
        message_queue.append(chat)  #Adds the final text of chat to the global queue to be typed by the keyboard
    elif not manual_sql_parse(str(message.guild.id))==manual_sql_parse(str(guild_id)): #Checks if a message came from a specific guild and channel
        channel = client.get_channel(channel_id)    #Gets the authorized channel's access
        await channel.send('Intruder detected, from server "'+manual_sql_parse(str(message.guild))+'" '+manual_sql_parse(str(message.guild.id))+', channel "'+manual_sql_parse(str(message.channel))+'" '+manual_sql_parse(str(message.channel.id))+'.')  #Sends chat regarding the user of the bot to the authorized channel
        await message.channel.send('This is an unauthorized use of this bot, please remove this bot from your server.')   #Notifies the users that this bot is for private use
        return  #Exits the function and returns escaped string that prevents program to respond to chats with malicious intention

while True: #Repeats until user's confirmation of the inputted coordinate for screenshot purposes later on the bottom of the loop
    while True: #Repeats until user inputted a positive coordinate for the top-left corner of the screenshot
        print("Input top-left coordinate for screenshot:")  #Asks the user for top-left corner's coordinate
        print("X: ", end = '')   #X coordinate
        x = float(input()) #Gets the top-left's X coordinate
        print("Y: ", end = '')   #Y coordinate
        y = float(input()) #Gets the top-left's Y coordinate
        if x>=0 and y>=0: #Checks if the input is valid
            break   #Breaks from the inner loop

    while True: #Repeats until user inputted a reasonable coordinate for the bottom-right corner of the screenshot
        print("Input width and height for screenshot:")  #Asks the user for more of screenshot's properties
        print("width: ", end = '')   #Width
        w = float(input()) #Gets the width
        print("height: ", end = '')   #Height
        h = float(input()) #Gets the height
        if w>0 and h>0: #Checks if the input is valid
            break   #Breaks from the inner loop

    image = pyautogui.screenshot(region=(x,y,w,h))  #Screenshot the monitor according to the inputted coordinate once
    image.save(image_path)  #Saves the screenshot
    image.save(previous_image_path)  #Saves the screenshot to another file
    confirmation_image = cv2.imread(image_path) #Reads one of the image
    print("Please check "+image_path+" on the script's folder and confirm if the image did capture the chatbox fully. If the result is satisfactory, press \"Y\" to continue, or any other keys to repeat this process.")   #Asks for the user's confirmation whether the testing screenshot is spot on
    cv2.imshow("confirmation image", confirmation_image)    #Shows the image
    cv2.waitKey(0)  #Waits for the form to be closed
    confirmation = input()  #Gets the user's confirmation
    if confirmation == 'Y': #Checks if the user's confirmation is Y
        break   #Exits the setup

client.run(token)   #Runs the bot

   
