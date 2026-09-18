"""Baja cierres de mercado con yfinance y escribe data/market_data.json.

Para cada activo calcula: último cierre, variación del día, de cinco ruedas y
en lo que va del año. En los bonos del Tesoro la variación va en puntos
básicos, que es como se mira.

Corre igual en GitHub Actions que en tu PC:
    python scripts/bajar_datos.py
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import yfinance as yf

from comun import ARCHIVO_DATOS, asegurar_carpetas, cargar_config, log


def _serie_cierres(ticker: str) -> pd.Series | None:
    inicio = date(date.today().year - 1, 12, 1)  # incluye el cierre del año previo
    try:
        df = yf.download(
            ticker,
            start=inicio.isoformat(),
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as e:
        log(f"  {ticker}: error al descargar ({e})")
        return None

    if df is None or df.empty:
        log(f"  {ticker}: sin datos")
        return None

    cierres = df["Close"]
    if isinstance(cierres, pd.DataFrame):  # yfinance a veces devuelve columnas multinivel
        cierres = cierres.iloc[:, 0]
    return cierres.dropna()


def _cierre_ano_previo(cierres: pd.Series) -> float | None:
    previos = cierres[cierres.index.year < date.today().year]
    return float(previos.iloc[-1]) if len(previos) else None


def _variacion(actual: float, anterior: float | None, como_tasa: bool) -> float | None:
    if anterior is None or anterior == 0:
        return None
    if como_tasa:
        return round((actual - anterior) * 100, 1)  # puntos básicos
    return round((actual / anterior - 1) * 100, 2)  # porcentaje


def construir_filas(config: dict) -> list[dict]:
    grupos = config["datos"]["grupos"]
    como_tasa = set(config["datos"].get("tickers_como_tasa", []))
    filas: list[dict] = []

    for grupo, activos in grupos.items():
        log(grupo)
        for nombre, ticker in activos.items():
            cierres = _serie_cierres(ticker)
            if cierres is None or len(cierres) < 2:
                filas.append({"grupo": grupo, "nombre": nombre, "ticker": ticker, "error": "sin datos"})
                continue

            es_tasa = ticker in como_tasa
            ultimo = float(cierres.iloc[-1])
            previo = float(cierres.iloc[-2])
            hace_cinco = float(cierres.iloc[-6]) if len(cierres) >= 6 else None

            filas.append(
                {
                    "grupo": grupo,
                    "nombre": nombre,
                    "ticker": ticker,
                    "unidad": "tasa" if es_tasa else "precio",
                    "fecha_cierre": cierres.index[-1].strftime("%Y-%m-%d"),
                    "ultimo": round(ultimo, 4 if es_tasa else 2),
                    "var_dia": _variacion(ultimo, previo, es_tasa),
                    "var_5_ruedas": _variacion(ultimo, hace_cinco, es_tasa),
                    "var_ytd": _variacion(ultimo, _cierre_ano_previo(cierres), es_tasa),
                }
            )
            log(f"  {nombre}: {round(ultimo, 2)}")

    return filas


def main() -> None:
    asegurar_carpetas()
    config = cargar_config()
    log("Bajando datos de mercado")
    filas = construir_filas(config)

    salida = {
        "generado_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "nota_unidades": "var_dia, var_5_ruedas y var_ytd van en % salvo unidad='tasa', donde van en puntos básicos",
        "filas": filas,
    }
    ARCHIVO_DATOS.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    fallidos = [f["nombre"] for f in filas if f.get("error")]
    log(f"Guardados {len(filas) - len(fallidos)} activos en {ARCHIVO_DATOS}")
    if fallidos:
        log(f"Sin datos: {', '.join(fallidos)}")


if __name__ == "__main__":
    main()
