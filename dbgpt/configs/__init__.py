"""TODO: Remove this file once we have a better way to handle the configs"""

import os
import random
import sys

from dotenv import load_dotenv

if "pytest" in sys.argv or "pytest" in sys.modules or os.getenv("CI"):
    print("Setting random seed to 42")
    random.seed(42)

# Load the users .env file into environment variables
load_dotenv(verbose=True, override=True)
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT_PATH, ".plugin_env"))

del load_dotenv

TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE = "knowledge_factory_domain_type"
TAG_KEY_KNOWLEDGE_CHAT_DOMAIN_TYPE = "knowledge_chat_domain_type"
DOMAIN_TYPE_FINANCIAL_REPORT = "FinancialReport"
