from browser_use.llm import ChatOpenAI
from browser_use import Agent, BrowserSession, Controller
from dotenv import load_dotenv
import os
import asyncio
from pydantic import BaseModel
from typing import List


load_dotenv()


class Post(BaseModel):
	post_title: str
	post_url: str
	num_comments: int
	hours_since_post: int

class Posts(BaseModel):
	posts: List[Post]

controller = Controller(output_model=Posts)

# Expand user directory for user_data_dir
user_data_dir = os.path.expanduser('~/.config/browseruse/profiles/default')

browser_session = BrowserSession(
    executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    user_data_dir=user_data_dir,
)

llm = ChatOpenAI(model="gpt-4.1")

async def main():
    agent = Agent(
        task="Can you webscrape this url and export the staff directory: only the names, positions, and emails. Export in csv and json format.  The url is: https://southwestmiamieagles.net/staff-directory/",
        llm=llm,
        browser_session=browser_session,
        controller=controller,
    )
    result = await agent.run()
    print(result.final_result())
    data = result.final_result()
    parsed: Posts = Posts.model_validate_json(data)
    print(parsed)
    await browser_session.close()

asyncio.run(main())

# Query: Can you webscrape this url and export the staff directory: only the names, positions, and titles. Export in csv format.  The url is : https://southwestmiamieagles.net/staff-directory/

