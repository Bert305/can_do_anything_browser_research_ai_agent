from browser_use.llm import ChatOpenAI
from browser_use import Agent, BrowserSession, Controller
from dotenv import load_dotenv
import os
import asyncio
import csv
from pydantic import BaseModel
from typing import List


load_dotenv()


class StaffRow(BaseModel):
    name: str
    position: str
    email: str

class StaffRows(BaseModel):
    rows: List[StaffRow]

controller = Controller(output_model=StaffRows)

# Expand user directory for user_data_dir
user_data_dir = os.path.expanduser('~/.config/browseruse/profiles/default')

browser_session = BrowserSession(
    executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    user_data_dir=user_data_dir,
)

llm = ChatOpenAI(model="gpt-4.1")

async def main():
    agent = Agent(
        task=(
            "Visit https://southwestmiamieagles.net/staff-directory/ and extract staff records. "
            "Return JSON only in this exact shape: "
            "{'rows':[{'name':'...','position':'...','email':'...'}]}. "
            "Include only rows where all three values are present."
        ),
        llm=llm,
        browser_session=browser_session,
        controller=controller,
    )
    result = await agent.run()
    data = result.final_result()
    parsed: StaffRows = StaffRows.model_validate_json(data)

    output_csv = "staff_directory.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "position", "email"])
        writer.writeheader()
        for row in parsed.rows:
            writer.writerow(row.model_dump())

    print(f"Saved CSV: {output_csv}")
    print(f"Rows exported: {len(parsed.rows)}")
    await browser_session.stop()

asyncio.run(main())

# Query: Can you webscrape this url and export the staff directory: only the names, positions, and titles. Export in csv format.  The url is : https://southwestmiamieagles.net/staff-directory/

