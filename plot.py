"""
Junta os resultados do Locust em planilhas e gera os gráficos.

Saídas:
    results/resumo.csv        -> uma linha por cenário (média, mediana, percentis, req/s, falhas)
    results/rampa_resumo.csv  -> com quantos usuários as falhas de cada API começaram na rampa
    results/rampa_serie.csv   -> curva da rampa (métricas por quantidade de usuários ativos)
    graficos/*.png            -> gráficos para a apresentação

Uso: .venv/bin/python plot.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PASTA_RESULTADOS = Path("results")
PASTA_GRAFICOS = Path("graficos")
PASTA_RAMPA = PASTA_RESULTADOS / "rampa"

# Cada linguagem tem sua cor e seu marcador
CORES = {"python": "#2a78d6", "ruby": "#eb6834"}
MARCADORES = {"python": "o", "ruby": "s"}

# Os gráficos têm dois painéis lado a lado, um para cada modo de cache.
# Com escalas separadas, porque os tempos sem cache são muito maiores.
MODOS_CACHE = ["com-cache", "sem-cache"]
TITULOS_CACHE = {"com-cache": "Com cache", "sem-cache": "Sem cache"}


def ler_resultados():
    """Lê a linha "Aggregated" de cada CSV e monta uma tabela com todos os cenários."""
    linhas = []
    for arquivo in sorted(PASTA_RESULTADOS.glob("*_stats.csv")):
        # Nome do arquivo: <api>_<modo>_<usuarios>u_stats.csv  (ex.: python_com-cache_10u_stats.csv)
        api, modo, usuarios = arquivo.name.replace("_stats.csv", "").split("_")
        stats = pd.read_csv(arquivo)
        total = stats[stats["Name"] == "Aggregated"].iloc[0]

        linhas.append({
            "api": api,
            "cache": modo,
            "usuarios": int(usuarios.rstrip("u")),
            "requisicoes": total["Request Count"],
            "falhas": total["Failure Count"],
            "falhas_pct": round(100 * total["Failure Count"] / total["Request Count"], 1),
            "media_ms": round(total["Average Response Time"], 1),
            "mediana_ms": total["Median Response Time"],
            "p90_ms": total["90%"],
            "p95_ms": total["95%"],
            "p99_ms": total["99%"],
            "max_ms": round(total["Max Response Time"], 1),
            "req_por_s": round(total["Requests/s"], 1),
        })

    return pd.DataFrame(linhas).sort_values(["api", "cache", "usuarios"])


def grafico_por_usuarios(tabela, coluna, titulo, rotulo_y, arquivo):
    """Gráfico de linhas: eixo X = usuários, uma linha por API, um painel por modo de cache."""
    fig, paineis = plt.subplots(1, 2, figsize=(12, 5))

    for ax, modo in zip(paineis, MODOS_CACHE):
        dados_modo = tabela[tabela["cache"] == modo]
        for api, grupo in dados_modo.groupby("api"):
            ax.plot(grupo["usuarios"], grupo[coluna],
                    color=CORES[api], marker=MARCADORES[api],
                    linewidth=2, markersize=7, label=api.capitalize())

        ax.set_title(TITULOS_CACHE[modo], loc="left")
        ax.set_xlabel("Usuários virtuais")
        ax.set_ylabel(rotulo_y)
        ax.set_xticks(sorted(tabela["usuarios"].unique()))
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color="#e5e5e5")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)

    fig.suptitle(titulo, fontsize=15, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / arquivo, dpi=150)
    plt.close(fig)


def grafico_percentis(tabela, usuarios, arquivo):
    """Barras com mediana, p90, p95 e p99 de cada API, para uma quantidade fixa de usuários."""
    fig, paineis = plt.subplots(1, 2, figsize=(12, 5))

    for ax, modo in zip(paineis, MODOS_CACHE):
        dados = tabela[(tabela["usuarios"] == usuarios) & (tabela["cache"] == modo)].copy()
        dados["api"] = dados["api"].str.capitalize()
        dados = dados.set_index("api")[["mediana_ms", "p90_ms", "p95_ms", "p99_ms"]]
        dados.columns = ["Mediana", "p90", "p95", "p99"]

        dados.plot.bar(ax=ax, rot=0, width=0.8, edgecolor="white", linewidth=2,
                       color=["#b9d3f3", "#7aaee8", "#2a78d6", "#1a4f91"])

        ax.set_title(TITULOS_CACHE[modo], loc="left")
        ax.set_xlabel("")
        ax.set_ylabel("Tempo de resposta (ms)")
        ax.grid(axis="y", color="#e5e5e5")
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)

    fig.suptitle(f"Percentis do tempo de resposta com {usuarios} usuários",
                 fontsize=15, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / arquivo, dpi=150)
    plt.close(fig)


def ler_rampa():
    """Lê o histórico segundo a segundo de cada teste de rampa (results/rampa/*_stats_history.csv)."""
    tabelas = []
    for arquivo in sorted(PASTA_RAMPA.glob("*_stats_history.csv")):
        # Nome do arquivo: <api>_<modo>_stats_history.csv  (ex.: python_com-cache_stats_history.csv)
        api, modo = arquivo.name.replace("_stats_history.csv", "").split("_")
        historico = pd.read_csv(arquivo)
        historico = historico[(historico["Name"] == "Aggregated") & (historico["User Count"] > 0)].copy()
        historico["api"] = api
        historico["cache"] = modo
        historico["falhas_pct"] = (100 * historico["Failures/s"] / historico["Requests/s"]).fillna(0)
        tabelas.append(historico)
    return pd.concat(tabelas)


def resumir_rampa(rampa, curva):
    """Para cada teste de rampa: com quantos usuários as falhas começaram.

    "primeira falha" pode ser um caso isolado; "falhas acima de 1%" mostra quando
    as falhas passam a ser frequentes (usando a curva suavizada).
    """
    linhas = []
    for (api, modo), historico in rampa.groupby(["api", "cache"]):
        com_falha = historico[historico["Total Failure Count"] > 0]
        curva_api = curva[(curva["api"] == api) & (curva["cache"] == modo)]
        acima_de_1pct = curva_api[curva_api["falhas_pct"] >= 1]
        linhas.append({
            "api": api,
            "cache": modo,
            "usuarios_na_primeira_falha": com_falha["User Count"].iloc[0] if len(com_falha) else None,
            "usuarios_com_falhas_acima_de_1pct": acima_de_1pct["usuarios"].iloc[0] if len(acima_de_1pct) else None,
            "max_usuarios": historico["User Count"].max(),
            "total_requisicoes": historico["Total Request Count"].iloc[-1],
            "total_falhas": historico["Total Failure Count"].iloc[-1],
            "maior_vazao_req_por_s": round(historico["Requests/s"].max(), 1),
        })
    return pd.DataFrame(linhas)


def curva_rampa(rampa):
    """Uma linha por (api, cache, usuários ativos), com as métricas suavizadas.

    Usa média móvel de 5 segundos para reduzir a oscilação de segundo a segundo.
    """
    curva = (rampa.groupby(["api", "cache", "User Count"])[["Requests/s", "falhas_pct", "50%"]]
             .mean().reset_index())
    curva.columns = ["api", "cache", "usuarios", "req_por_s", "falhas_pct", "mediana_ms"]

    metricas = ["req_por_s", "falhas_pct", "mediana_ms"]
    curva[metricas] = (curva.groupby(["api", "cache"])[metricas]
                       .transform(lambda coluna: coluna.rolling(5, min_periods=1).mean())
                       .round(1))
    return curva


def grafico_rampa(curva, resumo, coluna, titulo, rotulo_y, arquivo):
    """Gráfico da rampa: eixo X = usuários ativos naquele segundo, um painel por modo de cache.

    A linha pontilhada vertical marca onde as falhas de cada API passam de 1%.
    """
    fig, paineis = plt.subplots(1, 2, figsize=(12, 5))

    for ax, modo in zip(paineis, MODOS_CACHE):
        for api, grupo in curva[curva["cache"] == modo].groupby("api"):
            ax.plot(grupo["usuarios"], grupo[coluna],
                    color=CORES[api], linewidth=2, label=api.capitalize())

            linha_resumo = resumo[(resumo["api"] == api) & (resumo["cache"] == modo)]
            usuarios = linha_resumo["usuarios_com_falhas_acima_de_1pct"].iloc[0]
            if pd.notna(usuarios):
                ax.axvline(usuarios, color=CORES[api], linestyle=":", linewidth=1.5)

        ax.set_title(TITULOS_CACHE[modo], loc="left")
        ax.set_xlabel("Usuários virtuais ativos")
        ax.set_ylabel(rotulo_y)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color="#e5e5e5")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)

    fig.suptitle(titulo + "  (linha pontilhada = falhas passam de 1%)", fontsize=15, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(PASTA_GRAFICOS / arquivo, dpi=150)
    plt.close(fig)


def main():
    PASTA_GRAFICOS.mkdir(exist_ok=True)

    tabela = ler_resultados()
    tabela.to_csv(PASTA_RESULTADOS / "resumo.csv", index=False)
    print(tabela.to_string(index=False))

    grafico_por_usuarios(tabela, "media_ms", "Tempo médio de resposta",
                         "Tempo (ms)", "1_tempo_medio.png")
    grafico_por_usuarios(tabela, "mediana_ms", "Mediana do tempo de resposta",
                         "Tempo (ms)", "2_mediana.png")
    grafico_por_usuarios(tabela, "p95_ms", "Percentil 95 do tempo de resposta",
                         "Tempo (ms)", "3_p95.png")
    grafico_por_usuarios(tabela, "req_por_s", "Vazão (requisições por segundo)",
                         "Requisições/s", "4_vazao.png")
    grafico_por_usuarios(tabela, "falhas_pct", "Requisições com falha",
                         "Falhas (%)", "5_falhas.png")
    grafico_percentis(tabela, tabela["usuarios"].max(), "6_percentis_max_usuarios.png")

    # Teste de rampa (só se ele já tiver sido executado com ./run_rampa.sh)
    if list(PASTA_RAMPA.glob("*_stats_history.csv")):
        rampa = ler_rampa()
        curva = curva_rampa(rampa)
        curva.to_csv(PASTA_RESULTADOS / "rampa_serie.csv", index=False)

        resumo_rampa = resumir_rampa(rampa, curva)
        resumo_rampa.to_csv(PASTA_RESULTADOS / "rampa_resumo.csv", index=False)
        print("\nTeste de rampa:")
        print(resumo_rampa.to_string(index=False))

        grafico_rampa(curva, resumo_rampa, "falhas_pct", "Rampa: requisições com falha",
                      "Falhas (%)", "7_rampa_falhas.png")
        grafico_rampa(curva, resumo_rampa, "req_por_s", "Rampa: vazão",
                      "Requisições/s", "8_rampa_vazao.png")
        grafico_rampa(curva, resumo_rampa, "mediana_ms", "Rampa: mediana do tempo de resposta",
                      "Tempo (ms)", "9_rampa_mediana.png")

    print(f"\nGráficos salvos em {PASTA_GRAFICOS}/")


if __name__ == "__main__":
    main()
