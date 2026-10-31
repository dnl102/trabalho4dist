#!/usr/bin/env bash
# Teste de rampa: a quantidade de usuários cresce aos poucos (1 novo usuário por segundo)
# até MAX_USUARIOS. O Locust registra as métricas a cada segundo em *_stats_history.csv,
# o que permite ver com quantos usuários os erros começam a aparecer.
#
# Uso: ./run_rampa.sh
#      MAX_USUARIOS=200 ./run_rampa.sh
set -e

MAX_USUARIOS=${MAX_USUARIOS:-300}
DURACAO="${MAX_USUARIOS}s"  # com 1 usuário/s, a rampa chega ao máximo no fim do teste

mkdir -p results/rampa

for cache in true false; do
  echo "### Subindo o ambiente com USE_CACHE=$cache"
  USE_CACHE=$cache docker compose up -d --build
  sleep 5  # tempo para as APIs ficarem prontas

  for api in python ruby; do
    if [ "$api" = "python" ]; then porta=5000; else porta=4567; fi
    if [ "$cache" = "true" ]; then modo="com-cache"; else modo="sem-cache"; fi
    nome="${api}_${modo}"
    echo "### Rampa: $nome"

    # Esvazia o cache para que todo teste comece nas mesmas condições
    docker compose exec -T redis redis-cli FLUSHALL > /dev/null

    # Reinicia a API para que um teste não seja afetado pelas conexões do anterior
    docker compose restart "api-$api" > /dev/null
    sleep 3

    .venv/bin/locust --headless --only-summary --exit-code-on-error 0 \
      --host "http://localhost:$porta" \
      --users "$MAX_USUARIOS" --spawn-rate 1 --run-time "$DURACAO" \
      --csv "results/rampa/$nome"
  done
done

echo "### Fim. Resultados em results/rampa/"
