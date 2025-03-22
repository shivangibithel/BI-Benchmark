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

warnings.filterwarnings("ignore")
logging.basicConfig(filename='./logger/qgen_logger_pridictive.log', level=logging.INFO, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')

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

    def get_predictive_prompt(self, schema):
        return """## Task:

You are an expert in Business Intelligence (BI) and Data Analytics. Your objective is to generate **predictive analytical questions** that help anticipate **future outcomes, trends, patterns, or business performance** using available historical and current data from a business dataset.

## What Are Predictive Analytical Questions?

Predictive questions focus on understanding **what is likely to happen in the future**, by uncovering **patterns, trends, and relationships in historical data that can be used to forecast future events, behaviors, or outcomes**.

Predictive analytics aims to answer questions like **what will happen, what is likely to occur, and which future outcome is probable based on past behavior and current attributes**.

## How Should These Questions Be Framed?

1. **Use business-friendly language** — business users do not refer to table or column names in queries.
2. **Avoid explicit mentions of table/column names** in the question text.
3. **Ensure each question reflects natural business thinking**.
4. **Questions should be self-contained and clear**, so they can be answered directly using the dataset.

## Complexity Levels

1. **Basic** – High-level predictive questions based on trends or likelihood
   *Example: “Which customers are more likely to reduce their engagement in the next quarter?”*

2. **Intermediate** – Prediction questions based on patterns in historical behavior across segments or dimensions
   *Example: “Which product categories are likely to see growth based on past performance across regions?”*

3. **Advanced** – Multi-factor prediction questions involving multiple variables or risk identification
   *Example: “Which factors best predict customer churn risk in the next quarter?”*

## Instructions:

1. Generate exactly **9 predictive questions** in total : **3 Basic**, **3 Intermediate**, and **3 Advanced**.
2. Each question must be **realistically and fully answerable using the given dataset schema only**.
3. **Avoid questions that require any external or unavailable data.**
4. Use specific **business contexts** like customer behavior, product sales, regional trends, time-based forecasting - only when such dimensions are clearly available in the schema.
5. **Avoid mentioning actual table or column names in the question text.**
6. **Enclose each question within `<question>...</question>` tags.**
7. Return a clean, structured output in JSON format with each question and its complexity level.
8. **Again, do not return anything except the raw JSON array. Avoid any headings, notes, or boxed formats.**
9. All 9 questions must be returned in a **single flat JSON array**.
10. Do **not create multiple arrays or group questions by complexity** — just one array with 9 JSON objects.

Ensure:

1. Each question must be **strictly grounded in the dataset schema**. If the schema does not include a particular variable, behavior, or entity, do not generate a question about it.
2. **Do not invent, infer, or assume the presence of additional data, columns, or derived variables.**
3. Do not reference external or hypothetical factors such as market demand, customer sentiment, seasonality, or operational strategy unless clearly reflected in the schema.
4. Do not use vague phrases like "expected to grow", "future potential", or "market trends" unless such trends can be derived directly from existing schema fields.
5. Only formulate questions that can be answered using patterns, distributions, associations, or forecasts from **columns explicitly provided in the schema**.
6. Do not assume the presence of specific timeframes, demographic groups, or entity subtypes (e.g., premium customers, age groups, cities, seasons) unless these are **explicitly available** in the dataset schema.
  - Prefer phrasing like: *“across segments”, “based on available categories”, “by available types or groups”*.
  - Avoid: *“last year”, “city-wise”, “VIP customers”* if such values are not available in the schema.
7. Ensure that **each question is practically executable** using typical data analysis or forecasting methods applied to the dataset.

## Dataset Schema:

""" + schema + """

## Output Format:

```json
[
  {
    "question": "<question_text>",
    "complexity": "Basic | Intermediate | Advanced"
  }
]

Return a single JSON array named `questions`, not multiple arrays."""


    def postprocess_response(self, response):
        # Find all question entries
        json_str = response.split("json")[1].split("]")[0] +"]"
        print("#########################################");
        ques_complexity_list = ast.literal_eval(json_str)
        return ques_complexity_list
    
    def generate(self, database_name):
        ques_complexity_list, response = [],""
        try:
            table_names_query = "SHOW TABLES IN " + database_name + ";"
            input_tuples = run_query(exec_creds, table_names_query)
            database_tables = [item[0] for item in input_tuples]

            schema = schema_store.read_schema(self.schema_path, database_name, database_tables)

            prompt = self.get_predictive_prompt(schema)
            response = self.rits.post(input=prompt, temperature=self.temperature, max_new_tokens=self.max_new_tokens, repetition_penalty=self.repetition_penalty)
            logger.info("Questions generated:\n" + response)
            if response:
                ques_complexity_list = self.postprocess_response(response)
        except Exception as e:
            print(e);
            logger.error(e)
            return None
        finally:
            return ques_complexity_list

if __name__ == "__main__":
    schema_path = "./question_generation_benchmarking/database_schemas.json"
    benchmark = benchmarking(schema_path)
    input_tuples = run_query(exec_creds, "SHOW DATABASES;")
    database_names = [item[0] for item in input_tuples]
    database_names.remove("information_schema")
    database_names.remove("mysql")
    database_names.remove("performance_schema")
    database_names.remove("sys")

    ques = {}
    database_names = ["EU_SOCCER","E_COMMERCE","F1","GITHUB_REPOS","GOOGLE_ADS","GOOGLE_TRENDS","HUMAN_GENOME_VARIANTS","IDC","IOWA_LIQUOR_SALES","IPL","LOG","MUSIC","ORACLE_SQL","PAGILA","PANCANCER_ATLAS_1","PATENTS_GOOGLE","SQLITE_SAKILA","STACKING","TCGA_HG19_DATA_V0","THELOOK_ECOMMERCE","WWE"]
    for i in database_names:
        print(i)
        ques[i] = benchmark.generate(i)
        # break
    
    file_path = "./question_generation_benchmarking/question_jsons/predictive_questions2.json"
    with open(file_path, "w") as file:
        json.dump(ques, file)

    print(ques)
