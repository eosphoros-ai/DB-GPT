class DbDataLoader:
    def get_table_view_by_conn(self, data, speak):
        import pandas as pd

        ### tool out data to table view
        if len(data) <= 1:
            data.insert(0, ["result"])
        df = pd.DataFrame(data[1:], columns=data[0])
        html_table = df.to_html(index=False, escape=False, sparsify=False)
        table_str = "".join(html_table.split())
        html = f"""<div class="w-full overflow-auto">{table_str}</div>"""
        view_text = f"##### {str(speak)}" + "\n" + html.replace("\n", " ")
        return view_text
