def remove_sql_comments(sql: str) -> str:
    """Remove SQL comments while preserving quoted strings and identifiers.

    This is a small lexical scan, not a full SQL parser. It recognizes SQL's
    doubled-quote escaping so comment markers inside quoted regions remain
    part of the value or identifier.
    """
    result = []
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        if char in ("'", '"', "`"):
            quote = char
            result.append(char)
            index += 1

            while index < length:
                char = sql[index]
                result.append(char)
                index += 1

                if char == quote:
                    if index < length and sql[index] == quote:
                        # SQL-standard escaping: '' / "" / ``.
                        result.append(sql[index])
                        index += 1
                    else:
                        break
            continue

        if sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            if newline == -1:
                break
            # Keep the former behavior: the line-comment marker and its
            # terminating newline are both removed.
            index = newline + 1
            continue

        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end == -1:
                # Match the former behavior for an unterminated block comment.
                result.append(sql[index:])
                break
            index = end + 2
            continue

        result.append(char)
        index += 1

    return "".join(result)
