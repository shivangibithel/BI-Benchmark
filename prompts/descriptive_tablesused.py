import json
from rits.rits_runner import RITS
import os
import warnings
import logging
from config_full import get_settings
from dotenv import load_dotenv
load_dotenv()
import ast
from schema_linking import schema_store
from sql_components.executor import ExecutorCreds, SQLQueryExecutor
# export PYTHONPATH="${PYTHONPATH}:/home/shivangi/data-to-story"
warnings.filterwarnings("ignore")
logging.basicConfig(filename='/home/shivangi/data-to-story/benchmarking/qgen_logger_descriptive.log', level=logging.INFO, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

host = get_settings().mysql_host
user = get_settings().mysql_user
pswd = os.getenv('MYSQL_PASSWORD')
port = get_settings().mysql_port

exec_creds = ExecutorCreds(
    host=host,
    user=user,
    password=pswd,
    port=port
)

def run_query(exec_creds, query):
  return SQLQueryExecutor(exec_creds).run(query)

class benchmarking():
    def __init__(self, schema_path, apikey=os.getenv('RITS_APIKEY'), url=get_settings().rits_llama_url, model_id=get_settings().model_llama):
        self.schema_path = schema_path
        self.repetition_penalty = 1.02
        self.max_new_tokens = 500
        self.min_new_tokens = 1
        self.temperature = 0.05
        self.q_count_threshld = 9
        model_id = "meta-llama/llama-3-3-70b-instruct"
        url = "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/llama-3-3-70b-instruct/v1/completions"
        self.rits = RITS(uri=url, api_key=apikey, model_name=model_id)

    def get_descriptive_prompt(self, schema, question):
        return """## Task:

You are given a dataset schema and a natural language question.

Your task is to identify the **minimum set of tables required to answer the question**, based strictly on the columns available in each table.

### Instructions:
1. Carefully analyze the question and identify what data elements are required to answer it.
2. Refer to the dataset schema and determine which tables contain those elements.
3. Select **only the relevant tables** — avoid including unnecessary ones.
4. **Do not guess or assume columns/tables that are not explicitly in the schema.**
5. Return the output as a clean **flat JSON array of table names**, without any extra text, formatting, or explanations.
6. Do **not return any explanation or additional formatting**.
7. **Do not print multiple separate JSON arrays — return just one complete JSON array.**

### Input:
**Schema:**

""" + schema + """

**Question:**

""" + question + """

### Output Format:
```json
["TABLE_NAME_1", "TABLE_NAME_2"]"""

    def postprocess_response(self, response):
        # Find all question entries
        json_str = response.split("json")[1].split("]")[0] +"]"
        print("#########################################");
        table_used_list = ast.literal_eval(json_str)
        return table_used_list
    
    def generate(self, database_name, question):
        table_used_list, response = [], ""
        try:
            table_names_query = "SHOW TABLES IN " + database_name + ";"
            input_tuples = run_query(exec_creds, table_names_query)
            database_tables = [item[0] for item in input_tuples]

            schema = schema_store.read_schema(self.schema_path, database_name, database_tables)
            
            prompt = self.get_descriptive_prompt(schema, question)
            response = self.rits.post(input=prompt, temperature=self.temperature, max_new_tokens=self.max_new_tokens, repetition_penalty=self.repetition_penalty)
            logger.info("Table_used response:\n" + response)
            if response:
                table_used_list = self.postprocess_response(response)
        except Exception as e:
            print(e);
            logger.error(e)
            return None
        finally:
            return table_used_list

if __name__ == "__main__":
    schema_path = "/home/shivangi/data-to-story/benchmarking/database_schemas.json"
    benchmark = benchmarking(schema_path)
    input_tuples = run_query(exec_creds, "SHOW DATABASES;")
    database_names = [item[0] for item in input_tuples]
    database_names.remove("information_schema")
    database_names.remove("mysql")
    database_names.remove("performance_schema")
    database_names.remove("sys")

    with open("./question_generation_benchmarking/question_jsons/descriptive_questions.json", "r") as file:
        loaded_dict = json.load(file)
    
    # loaded_dict = {"AIRLINES": [{"question": "<What was the total number of flights operated by each aircraft type?>", "complexity": "Basic"}, {"question": "<What is the average range of aircraft used for flights?>", "complexity": "Basic"}, {"question": "<How many unique aircraft codes are there in the fleet?>", "complexity": "Basic"}, {"question": "<How do the scheduled departure and arrival times vary across different airports?>", "complexity": "Intermediate"}, {"question": "<What are the most common fare conditions for tickets sold?>", "complexity": "Intermediate"}, {"question": "<How does the total amount spent on bookings change over time?>", "complexity": "Intermediate"}, {"question": "<Which aircraft types have the longest and shortest ranges, and how do these compare to the average range of all aircraft?>", "complexity": "Advanced"}, {"question": "<What are the top destinations for flights based on the number of flights and the total amount earned from ticket sales?>", "complexity": "Advanced"}, {"question": "<How does the distribution of fare conditions change across different flight statuses, such as scheduled, cancelled, or delayed flights?>", "complexity": "Advanced"}]}
    
    # Process the data
    updated_dict = {}
    for table_name, questions in loaded_dict.items():
        updated_questions = []
        for item in questions:
            question_text = item["question"].strip('<>')
            table_used = benchmark.generate(table_name, question_text)  # Get table mapping dynamically
            updated_item = {
                "question": question_text,
                "complexity": item["complexity"],
                "table_used": table_used
            }
            updated_questions.append(updated_item)
        updated_dict[table_name] = updated_questions
    
    file_path = "./question_generation_benchmarking/question_jsons/descriptive_questions_with_tableused.json"
    with open(file_path, "w") as file:
        json.dump(updated_dict, file)
    print(updated_dict)
