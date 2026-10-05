# Remember the Seasons

![Remember the Seasons](visual/banner.png)

**[English](README.md)** · **Español** · **[Technical README](TECHNICAL.md)**

> Nos pidieron construir la próxima frontera de la IA. No podemos
> afirmar que la revolucionamos. Este es nuestro mejor intento en un mes.

> ESTADO: fase de investigación cerrada; el prototipo funcional vive en
> `product/`. Las fuentes siguen read-only, las afirmaciones etiquetadas,
> y los límites honestos están en el Technical README — no escondidos.

## El problema

Un agente puede recordar un hecho. ¿Puede explicar *por qué* lo sabe?

El retrieval responde "qué es similar a esta pregunta". No responde:
por qué esa memoria estaba disponible, qué decisión dependía de ella,
qué cambiaría si un evento histórico no hubiera pasado, o si la
respuesta que dio el mes pasado seguiría valiendo. Para un asistente
personal, un agente de debugging o un auditor, el *por qué* es el
producto.

Este repositorio investiga — y luego construye — memoria que conserva
las dos cosas: el estado que necesita para comportarse, y la historia
que necesita para explicar ese estado.

**Quién lo necesita**: equipos que despliegan agentes de vida larga y
ven el comportamiento derivar con semanas de memoria acumulada — sin
poder explicar qué cambio lo produjo. El retrieval actual muestra qué
se recuperó; no puede probar qué transición histórica alteró al
agente. Acá la prueba es el producto.

## NVIDIA Nemotron + Nebius — la interfaz de razonamiento, no un ornamento

Dos dependencias de modelo son partes estructurales de la solución,
ambas servidas por **Nebius Token Factory**:

- **`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`** interpreta la consulta,
  razona sobre las memorias recuperadas, declara cuáles usó y redacta
  la respuesta.
- **`Qwen/Qwen3-Embedding-8B`** produce los embeddings de retrieval
  sobre los que el campo adaptativo rankea.

Ninguno toca el estado. La declaración `used` del modelo es un
*claim*, registrado como tal; solo el motor determinístico decide
qué pasa a `reinforced` y cambia el campo. Esa frontera no es un
workaround de la constraint del hackathon — es la respuesta del
producto a la pregunta real "¿cómo metés un modelo generativo dentro
de memoria persistente sin dejar que su propia narrativa reescriba el
pasado que narra?". Nemotron participa causalmente; el protocolo
conserva la autoridad.

## Qué hace — observable primero

`product/demo.py` corre el claim completo (offline, determinístico;
una key de Nebius lo cambia a modelos reales):

```
ask: 'What do I need before deploying?'
served:    ['mem-0000','mem-0001']   <- lo que retrieval ofreció
used:      ['mem-0000','mem-0001']   <- lo que el modelo declaró
reinforced:['mem-0000','mem-0001']   <- lo que el motor honró
receipt: 1b2107b9… — sellado, rejugable, verificable independientemente

más tarde, la misma pregunta   → otro served, otro receipt
season(q, as_of=t1)            → el pasado recomputado, no un snapshot
do(T_i=∅) sobre una promoción  → el top-1 se invierte; el reporte
                                  sella exactamente qué transición lo causó
```

El mismo script con key:

```bash
NEBIUS_API_KEY=... python3 product/demo.py
# Nemotron-3-Nano (chat) + Qwen3-Embedding-8B en Nebius Token Factory
```

## Por qué es distinto

| Memoria por retrieval típica | Este sistema |
|---|---|
| devuelve documentos similares | sirve memorias *y* sella el receipt |
| sin registro de por qué respondió | decision record: uso declarado vs
corroborado, en la cadena |
| "confiá en el embedding" | el modelo declara; solo la corroboración
determinística cambia el campo |
| logs de lo que pasó | custody chains hash-linked — tamper-evident |
| no responde "¿y si no hubiera pasado?" | `do(T_i=∅)` excisa una
transición, rejuega el recall de producción, sella el delta |
| proximidad temporal implica causa | solo las `causes[]` declaradas
matan — un reloj no es una causa |

## Cómo funciona — tres capas

```
estado operacional      el campo adaptativo: reinforcement, promoción,
                        taint, links resonantes — lo que cambia
                        el comportamiento ahora
trayectoria forense     custody chains por memoria + ledger de
                        autoridad + receipts + decision records +
                        causes[] — por qué ese estado existe
replay contrafáctico    do(T_i=∅): excisa una transición, corre el
                        recall de producción en un SAVEPOINT,
                        rollback, compara — si esa transición importó
```

El LLM interpreta preguntas y redacta respuestas. Nunca fija estado:
*declara* qué memorias usó, y el motor determinístico decide qué
declaraciones se corroboran. Después de trece experimentos matando
autoridad semántica accidental, el modelo es subordinado del
protocolo — por diseño.

## La evidencia

- **Investigación**: `experiments/` — Exp19–35, la cadena de
  falsificación (`docs/HYPOTHESES.md`, `docs/EXPERIMENTS.md`).
- **Conformidad de protocolo**: `mneme-cf-bundle/v1` + `cf-cascade/v2`
  + `causal_ontology 2.0.0` — un verificador Go escrito de cero
  reproduce cada veredicto: **18/18 artifacts coinciden**, el corpus
  se regenera byte-por-byte, y CI lo impone en cada push.
- **Ontología causal**: spec `product/spec/causal-ontology-v2.md` —
  `causes[]` explícitas, invalidación por clausura transitiva; la
  adyacencia sola ya no mata nada.
- **Serie stigmergy adversarial**: `product/tests/test_stigmergy_pure.py`
  — 16 invariantes sobre escritura concurrente multi-autoridad.
  Encontró races reales (ya corregidas), demostró que serialización
  no es causalidad, que legalidad no es confluencia, y terminó en una
  frontera documentada: el registro sellado todavía no distingue
  concurrente de ordenado.

## Layout

```
remember-the-seasons/
  sources/       snapshots read-only de investigación (raven-memory,
                 mneme, stigmergy — cada uno con PROVENANCE.md)
  research/      inventarios de arqueología, mapas de mecanismos
  experiments/   Exp19–Exp35 — la cadena de falsificación
  docs/          paquete de investigación, hipótesis, stop conditions
  product/       el esqueleto funcional — ver product/README.md
    mneme/       custodia, autoridad, receipts, claims, canonical JSON
    seasons/     el agente: campo, wiring embed/LLM, trayectoria,
                 import de vaults, MCP
    tests/       suites de invariantes (trajectory, bundle, stigmergy)
    spec/        specs de protocolo (cf-bundle/v1, causal-ontology/v2)
    conformance/ corpus sellado + diferencial Python↔Go
```

## Probarlo

```bash
cd product
python3 demo.py                     # offline, determinístico
python3 tests/test_stigmergy_pure.py
python3 conformance/cf/v1/generate.py --check   # drift del corpus
bash conformance/cf/v1/differential.sh          # Python ↔ Go, 18/18
```

Arquitectura profunda, versiones de protocolo, modelo de amenazas,
alcance del determinismo y la lista honesta de lo que esto NO
garantiza: **[TECHNICAL.md](TECHNICAL.md)**.

## Reglas vigentes

Ver `AGENTS.md`. En particular: nada de commit/push sin autorización
explícita; `sources/` es read-only; cada afirmación va etiquetada
OBSERVED / INFERRED / PROPOSED / UNKNOWN.

## Licencia y atribución

Apache-2.0, Copyright 2026 Anna Tchijova — ver `LICENSE`. Créditos de
los sistemas fuente, corpus de métodos y runtime en `NOTICE`.
