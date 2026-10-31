"""
Usuário virtual do teste de carga do Link Extractor.

Cada usuário virtual faz uma sequência de 10 chamadas à API de extração de links,
passando uma URL diferente em cada chamada. Ao terminar a sequência, espera 1 segundo
e começa de novo, até o fim do teste.

Exemplo de uso (API Python, 10 usuários, 60 segundos):
    locust --headless --host http://localhost:5000 -u 10 -r 10 -t 60s
"""
from locust import HttpUser, task, constant

# As 10 URLs passadas para a API (servidas pelo container "sites")
URLS = [f"http://sites/pagina{i}.html" for i in range(1, 11)]

# Requisições mais lentas que isso contam como falha.
# Sem timeout, elas nunca terminariam e sumiriam das estatísticas.
TIMEOUT_SEGUNDOS = 10


class UsuarioLinkExtractor(HttpUser):
    wait_time = constant(1)  # pausa entre uma sequência e outra

    @task
    def extrair_links_de_10_urls(self):
        for url in URLS:
            # "name" agrupa as estatísticas por página no relatório
            nome_pagina = url.replace("http://sites/", "")
            self.client.get(f"/api/{url}", name=nome_pagina,
                            timeout=TIMEOUT_SEGUNDOS)
