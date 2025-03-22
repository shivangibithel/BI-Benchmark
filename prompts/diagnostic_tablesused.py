import json
import csv
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

warnings.filterwarnings("ignore")
logging.basicConfig(filename='/home/shivangi/data-to-story/benchmarking/qgen_logger_diagnostic.log', level=logging.INFO, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')

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
# export PYTHONPATH="${PYTHONPATH}:/home/shivangi/data-to-story"

class benchmarking():
    def __init__(self, schema_path, apikey=os.getenv('RITS_APIKEY'), url=get_settings().rits_llama_url, model_id=get_settings().model_llama):
        self.schema_path = schema_path
        self.repetition_penalty = 1.02
        self.max_new_tokens = 1500
        self.min_new_tokens = 1
        self.temperature = 0.05
        self.q_count_threshld = 9
        model_id = "meta-llama/llama-3-3-70b-instruct"
        url = "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/llama-3-3-70b-instruct/v1/completions"
        self.rits = RITS(uri=url, api_key=apikey, model_name=model_id)

    def get_descriptive_prompt(self, schema, question):
        return """## Task:

You are given a dataset schema and a diagnostic analytics question.  
Your goal is to identify the **minimum set of relevant tables** required to identify the **factors or variables that may explain or influence the outcome mentioned in the question**.

### Instructions:
1. Determine the column(s) that represent the **outcome or dependent variable** (e.g., cancellations, delays, etc.).
2. Identify **all possible influencing or explanatory variables (independent variables)** that could be analyzed to explain variation in the outcome.
3. Select **only those tables** that contain either the outcome variable itself or columns that can be logically used as influencing factors (such as aircraft, airport, fare type, flight details, etc.).
4. Include **supporting tables** only if they are joinable and provide useful context (e.g., aircraft or airport metadata).
5. Do not include tables that are **not relevant** to either the outcome or its potential influencing factors.
6. **Avoid listing redundant or unrelated tables.**
7. Do **not explain or justify your selections. Just return a JSON array** of table names.

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
    # File paths
    input_json_path = "/home/shivangi/data-to-story/question_generation_benchmarking/question_jsons/Diagnostic/diagnostic_questions.json"
    output_json_path = "./question_generation_benchmarking/question_jsons/diagnostic_questions_w_tableused2.json"
    # input_tuples = run_query(exec_creds, "SHOW DATABASES;")
    # database_names = [item[0] for item in input_tuples]
    # database_names.remove("information_schema")
    # database_names.remove("mysql")
    # database_names.remove("performance_schema")
    # database_names.remove("sys")

    database_names = ["IOWA_LIQUOR_SALES","IPL","LOG","MUSIC","ORACLE_SQL","PAGILA","PANCANCER_ATLAS_1","PATENTS_GOOGLE","SQLITE_SAKILA","STACKING","TCGA_HG19_DATA_V0","THELOOK_ECOMMERCE","WWE"]


    # with open("./question_generation_benchmarking/question_jsons/diagnostic_questions.json", "r") as file:
    #     loaded_dict = json.load(file)
    
    #     # Process the data
    # updated_dict = {}
    # for table_name, questions in loaded_dict.items():
    #     try:
    #         updated_questions = []
    #         for item in questions:
    #             question_text = item["question"].strip('<>')
    #             table_used = benchmark.generate(table_name, question_text)  # Get table mapping dynamically
    #             updated_item = {
    #                 "question": question_text,
    #                 "complexity": item["complexity"],
    #                 "table_used": table_used
    #             }
    #             updated_questions.append(updated_item)
    #         updated_dict[table_name] = updated_questions
    #     except:
    #         continue

    
    # file_path = "./question_generation_benchmarking/question_jsons/diagnostic_questions_w_tableused.json"
    # with open(file_path, "w") as file:
    #     json.dump(updated_dict, file)
    # print(updated_dict)

    # Load existing JSON data
    try:
        with open(output_json_path, "r") as file:
            existing_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = {}
    
    # Read new JSON data
    with open(input_json_path, "r") as file:
        new_data = json.load(file)
    
    # Process data and update
    for table_name, questions in new_data.items():
        updated_questions = []
        for item in questions:
            question_text = item["question"].strip("<>")
            complexity = item["complexity"].strip()
            
            table_used = benchmark.generate(table_name, question_text)  # Get table mapping dynamically
            updated_item = {
                "question": question_text,
                "complexity": complexity,
                "table_used": table_used
            }
            updated_questions.append(updated_item)
        
        if table_name in existing_data:
            existing_data[table_name].extend(updated_questions)
        else:
            existing_data[table_name] = updated_questions
    
    # Append updated data back to JSON file
    with open(output_json_path, "w") as file:
        json.dump(existing_data, file, indent=4)


