__all__ = ()

import pandas as pd

import requests


class MOEXService:
    BASE_URL = (
        "https://iss.moex.com/iss/history/engines/stock/markets/index/"
        "securities/IMOEX.json"
    )

    @classmethod
    def get_moex_index_series(cls, start_date, end_date):
        rows = []
        offset = 0

        while True:
            try:
                response = requests.get(
                    cls.BASE_URL,
                    params={
                        "from": start_date.isoformat(),
                        "till": end_date.isoformat(),
                        "start": offset,
                    },
                    timeout=3,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception:
                break

            history = payload.get("history", {})
            cols = history.get("columns", [])
            data = history.get("data", [])
            if not data:
                break

            rows.extend(data)
            offset += len(data)
            if len(data) < 100 or offset >= 200:
                break

        if not rows:
            return pd.Series(dtype=float)

        df = pd.DataFrame(rows, columns=cols)
        if "TRADEDATE" not in df.columns:
            return pd.Series(dtype=float)

        close_col = "CLOSE" if "CLOSE" in df.columns else "LEGALCLOSEPRICE"
        if close_col not in df.columns:
            return pd.Series(dtype=float)

        df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
        df["TRADEDATE"] = pd.to_datetime(df["TRADEDATE"])
        df = df.dropna(subset=[close_col]).drop_duplicates(
            subset=["TRADEDATE"],
        )
        if df.empty:
            return pd.Series(dtype=float)

        return pd.Series(
            df[close_col].values,
            index=df["TRADEDATE"],
        ).sort_index()
