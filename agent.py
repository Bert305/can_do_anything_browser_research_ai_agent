from browser_use.llm import ChatOpenAI
from browser_use import Agent, BrowserSession, Controller
from dotenv import load_dotenv
import os
import asyncio
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
import textwrap

load_dotenv()

# =============================================================================
# 🚀 CHANGE YOUR TASK HERE - This is the only thing you need to modify!
# =============================================================================
USER_TASK = "Give me the latest video games from store.playstation.com and summarize the top 5 trending games with their prices and release dates."
# # Current task
# USER_TASK = "Go search and extract data on the latest trends of nike products and nike news. Format the data clearly and give me a summary report."

# # Other examples:
# USER_TASK = "Go to amazon.com and extract the top 10 best-selling electronics with prices and ratings"
# USER_TASK = "Scrape job listings from LinkedIn for Python developer positions"
# USER_TASK = "Get the latest cryptocurrency prices from CoinMarketCap"
# USER_TASK = "Extract restaurant reviews from Yelp for NYC pizza places"
# USER_TASK = "Go to https://southwestmiamieagles.net/staff-directory/ and extract names, positions, and titles"
# Optional: Change the output filename (default: "web_scraping_results")
OUTPUT_FILENAME = "game_trends_report"
# =============================================================================

def create_pdf_report(data, filename, title="Web Scraping Report", description=""):
    """Create a formatted PDF report from scraped data"""
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, title, 0, 1, 'C')
            self.ln(10)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    pdf = PDF()
    pdf.add_page()
    
    # Add timestamp and description
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
    if description:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Task Description:", 0, 1)
        pdf.set_font('Arial', '', 10)
        wrapped_desc = textwrap.fill(description, width=80)
        for line in wrapped_desc.split('\n'):
            pdf.cell(0, 6, line.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Extracted Data:", 0, 1)
    pdf.ln(5)
    
    # Convert data to string if needed
    if isinstance(data, str):
        try:
            # Try to parse as JSON for better formatting
            parsed_data = json.loads(data)
            data_str = json.dumps(parsed_data, indent=2, ensure_ascii=False)
        except:
            data_str = data
    else:
        data_str = json.dumps(data, indent=2, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data)
    
    # Add data to PDF
    pdf.set_font('Arial', '', 9)
    wrapped_text = textwrap.fill(data_str, width=90)
    for line in wrapped_text.split('\n'):
        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 5, safe_line, 0, 1)
    
    return pdf

def save_data_to_files(data, filename, task_description=""):
    """Save scraped data to multiple file formats in the output directory"""
    
    # Create output directory
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)
    
    # Add timestamp to filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{filename}_{timestamp}"
    
    saved_files = []
    
    # Save as JSON
    try:
        json_path = output_dir / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            if isinstance(data, str):
                try:
                    parsed_data = json.loads(data)
                    json.dump(parsed_data, f, indent=2, ensure_ascii=False)
                except:
                    json.dump({"raw_data": data, "task": task_description}, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON saved: {json_path}")
        saved_files.append(json_path)
    except Exception as e:
        print(f"❌ Error saving JSON: {e}")
    
    # Save as TXT
    try:
        txt_path = output_dir / f"{base_name}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"Task: {task_description}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            
            if isinstance(data, str):
                f.write(data)
            else:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"✅ TXT saved: {txt_path}")
        saved_files.append(txt_path)
    except Exception as e:
        print(f"❌ Error saving TXT: {e}")
    
    # Save as PDF
    try:
        pdf_path = output_dir / f"{base_name}.pdf"
        pdf = create_pdf_report(data, filename, title=f"Web Scraping Report: {filename}", description=task_description)
        pdf.output(str(pdf_path))
        print(f"✅ PDF saved: {pdf_path}")
        saved_files.append(pdf_path)
    except Exception as e:
        print(f"❌ Error saving PDF: {e}")
    
    # Try to save as CSV if data is structured
    try:
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
                data = parsed_data
            except:
                pass
        
        if isinstance(data, dict):
            # Try to find list values for CSV
            list_values = [v for v in data.values() if isinstance(v, list) and len(v) > 0]
            if list_values:
                df = pd.DataFrame(list_values[0])
                csv_path = output_dir / f"{base_name}.csv"
                df.to_csv(csv_path, index=False, encoding='utf-8')
                print(f"✅ CSV saved: {csv_path}")
                saved_files.append(csv_path)
        elif isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)
            csv_path = output_dir / f"{base_name}.csv"
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"✅ CSV saved: {csv_path}")
            saved_files.append(csv_path)
    except Exception as e:
        print(f"⚠️  Could not save as CSV: {e}")
    
    return saved_files

# Browser session setup
user_data_dir = os.path.expanduser('~/.config/browseruse/profiles/default')
browser_session = BrowserSession(
    executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    user_data_dir=user_data_dir,
)
llm = ChatOpenAI(model="gpt-4.1")

async def main():
    """
    Simple web scraping function - just change USER_TASK at the top!
    """
    
    print("🚀 Starting Web Scraping Agent...")
    print(f"📋 Task: {USER_TASK}")
    print(f"💾 Output files will be saved as: {OUTPUT_FILENAME}_TIMESTAMP.*")
    print("-" * 60)
    
    # Create the agent
    agent = Agent(
        task=USER_TASK,
        llm=llm,
        browser_session=browser_session,
    )
    
    try:
        # Run the scraping task
        print("🌐 Agent is working...")
        result = await agent.run()
        raw_result = result.final_result()
        
        print("✅ Scraping completed!")
        print(f"📊 Data extracted: {len(str(raw_result))} characters")
        
        # Save to all file formats
        print("\n💾 Saving files...")
        saved_files = save_data_to_files(raw_result, OUTPUT_FILENAME, USER_TASK)
        
        print(f"\n🎉 All done! {len(saved_files)} files saved in the 'output' folder:")
        for file_path in saved_files:
            print(f"   📄 {file_path.name}")
            
        return raw_result
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        # Save error info
        error_info = {
            "error": str(e),
            "task": USER_TASK,
            "timestamp": datetime.now().isoformat()
        }
        save_data_to_files(error_info, f"{OUTPUT_FILENAME}_error", "Error occurred during scraping")
        
    finally:
        await browser_session.close()

if __name__ == "__main__":
    asyncio.run(main())

