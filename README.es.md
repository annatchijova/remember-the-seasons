# Remember the Seasons

> Nos pidieron construir la próxima frontera de la IA. No podemos
> afirmar que la revolucionamos. Este es nuestro mejor intento en un mes.

*(English: `README.md`)*

## Qué es esto

Un laboratorio de investigación que ya produjo sus respuestas — y un
producto mínimo construido sobre ellas.

La pregunta original:

> ¿Dónde deja de ser suficiente *retrieval* como modelo de memoria
> persistente de un agente, y qué mecanismos adicionales producen
> propiedades medibles que retrieval por sí solo no representa?

## Lo que la investigación respondió (Exp19–Exp35)

El estado adaptativo persistente **alcanza** para producir
path-dependence en este sistema: un flag binario ya genera divergencia
medible. Pero cuando intentamos explicar *qué parte de la historia
produjo* ese estado — duración, cantidad, posición — cada resumen
simple que probamos perdió estructura explicativa bajo controles
mejores. No demostramos que haga falta guardar toda la historia, ni
que no exista otra compresión suficiente: demostramos exactamente qué
información dejamos de poder explicar cada vez que comprimimos.

La separación arquitectónica que emergió:

```
estado requerido para comportarse   ≠   historia requerida para explicarlo
        (operacional, compacto)              (forense, verificable)
```

## El producto (`product/`)

Un agente de memoria personal donde esa separación es mecánica real:

- **Estado operacional**: field adaptativo — reinforcement, olvido,
  contradicciones, links resonantes que cambian el recall.
- **Trayectoria forense**: custody chains, receipts sellados,
  decision records — por qué el estado terminó así.
- **Replay contrafáctico**: `what_if_transition` excisa una transición
  histórica, corre el *mismo* recall de producción en un SAVEPOINT y
  hace rollback — "¿y si eso no hubiera pasado?" con delta sellado.

Capa PKM sobre eso: importar un vault Obsidian (`import_vault` —
`.md` → memorias, `[[wikilinks]]` → aristas RESONANT que *sí* cambian
el recall), edición como supersession con linaje, olvido/revivido
auditado, backlinks, search, CLI, MCP server, UI de demo.

Corre sobre **Nebius Token Factory** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
+ embeddings Qwen3-8B) con stub determinístico offline.

## Layout

```
remember-the-seasons/
  sources/      snapshots read-only: raven-memory, mneme, stigmergy
  research/     arqueología, mapas de mecanismos
  experiments/  Exp19–Exp35 — la cadena de falsificación
  docs/         paquete de investigación, hipótesis, condiciones de parada
  product/      el esqueleto de producto (ver product/README.md)
```

## Reglas vigentes

Ver `AGENTS.md`. En particular: nada de commit/push sin autorización
explícita; `sources/` es read-only; cada afirmación va etiquetada
OBSERVED / INFERRED / PROPOSED / UNKNOWN.

## Licencia y atribución

Apache-2.0, Copyright 2026 Anna Tchijova — ver `LICENSE`. Créditos de
los sistemas fuente, corpus de métodos y runtime en `NOTICE`.
