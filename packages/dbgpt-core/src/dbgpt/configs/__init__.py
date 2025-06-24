"""TODO: Remove this file once we have a better way to handle the configs"""

import os
import random
import sys

if "pytest" in sys.argv or "pytest" in sys.modules or os.getenv("CI"):
    print("Setting random seed to 42")
    random.seed(42)

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE = "knowledge_factory_domain_type"
TAG_KEY_KNOWLEDGE_CHAT_DOMAIN_TYPE = "knowledge_chat_domain_type"
DOMAIN_TYPE_FINANCIAL_REPORT = "FinancialReport"

VARIABLES_SCOPE_GLOBAL = "global"
VARIABLES_SCOPE_APP = "app"
VARIABLES_SCOPE_AGENT = "agent"
VARIABLES_SCOPE_FLOW = "flow"
VARIABLES_SCOPE_DATASOURCE = "datasource"
VARIABLES_SCOPE_FLOW_PRIVATE = "flow_priv"
VARIABLES_SCOPE_AGENT_PRIVATE = "agent_priv"
