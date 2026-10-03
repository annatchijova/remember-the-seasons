# product/ — Remember the Seasons (esqueleto)

*(English: `README.md` — traducción; el canónico es el inglés.)*

La investigación dijo:

> el estado requerido para comportarse ≠ la historia requerida para explicarlo

Este es el producto mínimo sobre esa separación: **mneme es la capa
forense** (custody chains, receipts sellados, decisiones, bundles) y
**seasons es el loop operacional encima** (guardar → recordar →
responder → reforzar). El estado adaptativo puede ser chico; la
trayectoria que escribe no.

## served ≠ used ≠ reinforced

`ask()` no los confunde. El recall sirve candidatos (receipt sellado);
el modelo responde y declara qué ids usó de verdad; solo los
declarados entran al decision record — y solo el subconjunto
**corroborado determinísticamente** gana reinforcement (solape
contenido-respuesta; ahí muere el payoff de manipular la declaración).
El canal de declaración lleva un nonce de sesión estilo Kassandra
(HMAC del receipt sellado, `RTS_KASSANDRA_SALT`): una línea `USED:`
sin él es forgery — detectada, ignorada, fallback determinístico.
Ver `REDTEAM.md`.

## El loop

```python
a = SeasonsAgent()
a.remember("The deploy gate requires staging to pass.")
r = a.ask("What do I need before deploying?")
```

`recall → receipt sellado → respuesta → decision record → reinforce`
solo de lo declarado y corroborado. Cada paso auditable.

## La primitiva del nombre

```python
s = a.season(question, as_of=t1)
```

La misma pregunta, en una season anterior del field: reconstruye el
estado por replay de chains truncadas en `t1`, sin snapshots. Una
"season" es un corte histórico verificable.

## Counterfactual

`a.what_if_transition(q, mem, seq)` — la misma query en el mundo donde
ese evento de custody no ocurrió: la chain se replaya sin el evento,
el recall real corre dentro de un SAVEPOINT y se hace rollback. Report
sellado con `hypothetical: true`.

`a.decision_what_if(dec, mem, seq)` — ¿la base de evidencia de esa
decisión sobrevive la excisión?

`a.request_provenance(trace, depth)` — fachada por niveles:
`summary | direct | impact | counterfactual`.

## La capa vault — la superficie PKM

`a.import_vault(path)`: cada `.md` → memoria con custody chain, cada
`[[wikilink]]` → arista RESONANT que cambia el recall de verdad.
`a.update(id, texto)` = supersession con linaje. `a.forget/revive` =
olvido auditado. Contradicciones se auto-detectan (INHIBITORY +
`CONTRADICTED_BY` en ambas chains).

Lo que Obsidian da: notas, links, grafo. Lo que esto agrega: cada nota
es historia verificable, cada link cambia conducta, cada edición tiene
linaje — y todo es replayeable, verificable y excisable.

## LLM

`NEBIUS_API_KEY` + `NEBIUS_BASE_URL` → chat + embeddings reales en
Token Factory (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` +
`Qwen/Qwen3-Embedding-8B`). Sin key: stub determinístico — mismos
receipts, cero modelo.

## MCP — el producto ES la herramienta

`seasons_mcp_server.py` (FastMCP stdio): cualquier agente MCP que lo
registre obtiene memoria verificable. 10 tools: `remember` `ask`
`season` `what_if_transition` `decision_what_if` `request_provenance`
`import_vault` `update` `forget` `revive` `link` `export_bundle`.

`server.py` — UI de demo humana (stdlib-only, :8420).
`python3 -m seasons` — CLI completo sobre `RTS_DB_PATH`.

## Latencia (bench.py, embedder offline)

| op | p50 @200 | p50 @1000 |
|---|---:|---:|
| recall | 38ms | 192ms |
| provenance/counterfactual | 1ms | 4ms |
| what_if_transition | 75ms | 379ms |
| export_bundle | 12ms | 50ms |

Recall es O(N) (~190μs/memoria); a ~10k notas se acerca al segundo —
un índice de embeddings lo arregla sin cambiar el protocolo.

## Estado

Esqueleto verificado end-to-end en Nebius Token Factory (requisito del
hackathon cumplido: ejecución Nebius + modelo NVIDIA open-source).
Audit red-team en `REDTEAM.md`. Limitaciones nombradas, no escondidas:
el counterfactual v1 es local (una transición/una chain); los links
explícitos no tienen custody event propio; no hay rewind causal global.
