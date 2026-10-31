#!/usr/bin/env bash
# Executa todos os cenários de teste e salva os CSVs do Locust na pasta results/.
#
# Cenários = (com cache, sem cache) x (Python, Ruby) x (quantidade de usuários)
#
# Uso: ./run_tests.sh            (60 segundos por cenário)
#      DURACAO=30s ./run_tests.sh
#      USUARIOS="10 50" ./run_tests.sh   (só algumas quantidades de usuários)
set -e

DURACAO=${DURACAO:-60s}
USUARIOS=${USUARIOS:-"1 10 25 50 75 100 150 200"}

mkdir -p results

for cache in true false; do
  echo "### Subindo o ambiente com USE_CACHE=$cache"
  USE_CACHE=$cache docker compose up -d --build
  sleep 5  # tempo para as APIs ficarem prontas

  for api in python ruby; do
    if [ "$api" = "python" ]; then porta=5000; else porta=4567; fi

    for u in $USUARIOS; do
      if [ "$cache" = "true" ]; then modo="com-cache"; else modo="sem-cache"; fi
      nome="${api}_${modo}_${u}u"
      echo "### Cenário: $nome"

      # Esvazia o cache para que todo cenário comece nas mesmas condições
      docker compose exec -T redis redis-cli FLUSHALL > /dev/null

      # --exit-code-on-error 0: requisições com falha fazem parte do resultado,
      # então não devem interromper o script
      .venv/bin/locust --headless --only-summary --exit-code-on-error 0 \
        --host "http://localhost:$porta" \
        --users "$u" --spawn-rate "$u" --run-time "$DURACAO" \
        --csv "results/$nome"
    done
  done
done

echo "### Fim. Resultados em results/"
