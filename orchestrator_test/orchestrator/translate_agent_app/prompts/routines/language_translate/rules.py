LANGUAGE_TRANSLATE_RULE = """
1. Call the 'initiate_config' function to finish the basic config 
2. Call the 'translate_judge' function to get a judgement about using 'short_translate' or 'long_translate' to translate.
3. If the judgement is True:
3a) Call the 'short_translate' function
4. If the judgement is False:
4a) Call the 'long_translate' function
5. If the judgement is another type of translate:
5a) Call the 'escalate_to_agent' function.
6.If the customer has no further questions, call the 'case_resolved' function.

**Case Resolved: When the case has been resolved, ALWAYS call the "case_resolved" function**
"""