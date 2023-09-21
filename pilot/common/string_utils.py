

def extract_content(long_string, s1, s2):
    start_index = long_string.find(s1)
    if start_index < 0:
        return ""
    end_index = long_string.find(s2, start_index + len(s1))
    extracted_content = long_string[start_index + len(s1):end_index]
    return extracted_content

def extract_content_open_ending(long_string, s1, s2):
    start_index = long_string.find(s1)
    if start_index < 0:
        return ""
    if  long_string.find(s2) <=0:
        end_index = len(long_string)
    else:
        end_index = long_string.find(s2, start_index + len(s1))
    extracted_content = long_string[start_index + len(s1):end_index]
    return extracted_content

def extract_content_include(long_string, s1, s2):
    start_index = long_string.find(s1)
    if start_index < 0:
        return ""
    end_index = long_string.find(s2, start_index + len(s1) + 1)
    extracted_content = long_string[start_index:end_index + len(s2)]
    return extracted_content

def extract_content_include_open_ending(long_string, s1, s2):

    start_index = long_string.find(s1)
    if start_index < 0:
        return ""
    if  long_string.find(s2) <=0:
        end_index = len(long_string)
    else:
        end_index = long_string.find(s2, start_index + len(s1) + 1)
    extracted_content = long_string[start_index:end_index + len(s2)]
    return extracted_content



if __name__=="__main__":
    s = "abcd123efghijkjhhh456"
    s1 = "123"
    s2 = "456"

    print(extract_content_open_ending(s, s1, s2))