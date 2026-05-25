#!/usr/bin/env python3
"""
Genera reporte científico del pipeline Soot/Jimple
Incluye comparación directa con LLVM IR para el paper
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).parent.resolve()
REPORT_DIR = BASE_DIR / "reports"
JIMPLE_DIR = BASE_DIR / "jimple"

def load_results():
    with open(str(REPORT_DIR / "soot_pipeline_results.json"), encoding="utf-8") as f:
        return json.load(f)

def read_jimple(name):
    try:
        return (JIMPLE_DIR / f"{name}.jimple").read_text(encoding="utf-8", errors="ignore")
    except:
        return "[archivo .jimple no disponible — requiere soot.jar]"

def generate_report(results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    a = lines.append

    a("# Hallazgos: Pipeline Java → Jimple IR (Soot)")
    a(f"**Fecha:** {now}  |  **Herramienta:** Soot 4.3.0  |  **Entorno:** OpenJDK 21")
    a("")
    a("---")
    a("")
    a("## 1. Resumen Ejecutivo")
    a("")
    total   = len(results)
    ok_java = sum(1 for r in results if r["javac"]["success"])
    ok_soot = sum(1 for r in results if r["soot"]["success"])
    ok_anal = sum(1 for r in results if r["analysis"]["success"])
    a(f"Se procesaron **{total} muestras** representativas de patrones Java comunes.")
    a(f"Compilación `javac`: **{ok_java}/{total}** exitosos.")
    a(f"Generación Jimple con Soot: **{ok_soot}/{total}** — requiere `soot.jar` en entorno con red.")
    a(f"Análisis de representación Jimple: **{ok_anal}/{total}** completados sobre archivos de referencia.")
    a("")
    a("**Conclusión preliminar:** Soot/Jimple es **significativamente más viable** que LLVM IR")
    a("para representar código Java. Maneja lambdas, excepciones, colecciones y herencia")
    a("de forma nativa sin los workarounds requeridos por LLVM IR.")
    a("")
    a("---")
    a("")
    a("## 2. Pipeline")
    a("")
    a("```")
    a("Java (.java)")
    a("    │")
    a("    ▼  javac 21")
    a("JVM Bytecode (.class)")
    a("    │")
    a("    ▼  Soot 4.3.0  (java -jar soot.jar -f jimple)")
    a("Jimple IR (.jimple)  →  Análisis de patrones y fingerprinting")
    a("```")
    a("")
    a("| Herramienta | Versión | Descarga |")
    a("|---|---|---|")
    a("| OpenJDK | 21 | preinstalado |")
    a("| Soot | 4.3.0 | [Maven Central](https://repo1.maven.org/maven2/org/soot-oss/soot/4.3.0/soot-4.3.0-jar-with-dependencies.jar) |")
    a("")
    a("**Comando Soot:**")
    a("```bash")
    a("java -jar soot.jar -cp bytecode/ -f jimple -d jimple/ -pp -allow-phantom-refs NombreClase")
    a("```")
    a("")
    a("---")
    a("")
    a("## 3. Resultados por Muestra")
    a("")

    # Tabla resumen
    a("| # | Sample | Categoría | javac | Jimple | Líneas Jimple | dynamicinvoke |")
    a("|---|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        javac = "✅" if r["javac"]["success"] else "❌"
        soot  = "✅" if r["soot"]["success"] else "⏳"
        lines_count = r["analysis"].get("line_count", "—")
        has_dynamic = "✅ sí" if "dynamicinvoke" in r["analysis"].get("invoke_types", {}) else "—"
        a(f"| {i} | `{r['name']}` | {r['category']} | {javac} | {soot} | {lines_count} | {has_dynamic} |")

    a("")

    # Detalle por sample
    for r in results:
        a(f"### {r['name']} — {r['description']}")
        a("")

        # Tipos de invoke (clave para plagio)
        inv = r["analysis"].get("invoke_types", {})
        if inv:
            a("**Instrucciones invoke detectadas** (relevantes para análisis de plagio):")
            for k, v in inv.items():
                a(f"- `{k}`: {v} ocurrencia(s)")
        a("")

        # Clases referenciadas
        classes = r["analysis"].get("unique_classes", [])
        if classes:
            a(f"**Clases JDK referenciadas:** `{'`, `'.join(classes[:8])}`")
        a("")

        # Comparación vs LLVM IR
        comp = r.get("vs_llvm", {})
        if comp:
            a("**Comparación directa vs LLVM IR:**")
            a(f"- LLVM IR generó: {comp.get('llvm_lines', '?')} líneas con limitaciones")
            a(f"- Limitación LLVM IR: {comp.get('llvm_limitation', '—')}")
            a(f"- Ventaja Jimple: {comp.get('jimple_advantage_detail', '—')}")
        a("")

        # Fragmento Jimple
        jimple_text = read_jimple(r['name'])
        a("**Jimple IR (fragmento):**")
        a("```java")
        for line in jimple_text.splitlines()[:25]:
            a(line)
        jimple_lines = jimple_text.splitlines()
        if len(jimple_lines) > 25:
            a(f"// ... ({len(jimple_lines) - 25} líneas adicionales)")
        a("```")
        a("")

    a("---")
    a("")
    a("## 4. Jimple vs LLVM IR — Comparación para el Paper")
    a("")
    a("| Característica Java | LLVM IR | Jimple (Soot) | Ganador |")
    a("|---|---|---|---|")
    a("| Aritmética y loops | ✅ Directo | ✅ Directo | Empate |")
    a("| Herencia / polimorfismo | ⚠️ vtable manual | ✅ `virtualinvoke` nativo | **Jimple** |")
    a("| Excepciones try/catch | ❌ ABI C++ externo | ✅ `catch` nativo | **Jimple** |")
    a("| Generics / colecciones | ❌ i8* opaco | ⚠️ `checkcast` explícito | **Jimple** |")
    a("| Lambdas / invokedynamic | ❌ Sin equivalente | ✅ `dynamicinvoke` + lambda$N | **Jimple** |")
    a("| Stream API | ❌ Reimplementación total | ✅ `interfaceinvoke` real | **Jimple** |")
    a("| Garbage Collector | ❌ No representable | ✅ Implícito (JVM) | **Jimple** |")
    a("| Biblioteca estándar (JDK) | ❌ Debe reimplementarse | ✅ Referenciada directamente | **Jimple** |")
    a("")
    a("---")
    a("")
    a("## 5. Relevancia para Detección de Plagio")
    a("")
    a("Jimple es especialmente útil para detección de plagio porque:")
    a("")
    a("**5.1 Normalización de nombres**")
    a("Soot renombra variables locales a `r0, r1, $i0, $i1...` — elimina el efecto de")
    a("renombrar variables, una técnica común de plagio superficial.")
    a("")
    a("**5.2 Fingerprinting por patrón de invoke**")
    a("La secuencia de `virtualinvoke / interfaceinvoke / staticinvoke` es característica")
    a("de la lógica del programa independientemente del estilo de escritura.")
    a("")
    a("**5.3 Clases JDK referenciadas como firma estructural**")
    a("Las clases del JDK que aparecen en el Jimple (`java.util.ArrayList`,")
    a("`java.util.HashMap`, etc.) forman una firma del comportamiento del programa.")
    a("")
    a("**5.4 Resistencia a ofuscación básica**")
    a("Como Jimple se genera desde bytecode compilado, no desde el texto fuente,")
    a("es resistente a cambios de formato, comentarios y nombres de variables.")
    a("")
    a("---")
    a("")
    a("## 6. Limitaciones de Soot/Jimple")
    a("")
    a("**L1 — Type erasure persiste:** `List<Integer>` sigue siendo `List` en Jimple,")
    a("con `checkcast` explícitos. Los tipos genéricos no se recuperan.")
    a("")
    a("**L2 — Inner classes como archivos separados:** Soot genera un `.jimple` por clase,")
    a("incluyendo clases internas (`Sample02_OOP$Circle.jimple`). Requiere manejo de múltiples archivos.")
    a("")
    a("**L3 — lambdas como métodos sintéticos:** Las lambdas se convierten en `lambda$main$0`,")
    a("`lambda$main$1`, etc. La semántica es correcta pero la estructura varía entre compilaciones.")
    a("")
    a("**L4 — Dependencia de la JDK:** Soot necesita acceso al `rt.jar` o equivalente")
    a("para resolver referencias a clases del JDK. En Java 11+, usar `-pp` (prepend).")
    a("")
    a("---")
    a("")
    a("## 7. Próximos Pasos")
    a("")
    a("- [ ] Descargar `soot.jar` y ejecutar `pipeline.py` para generar Jimple real (no de referencia)")
    a("- [ ] Ampliar dataset al muestreo balanceado acordado con el equipo")
    a("- [ ] Implementar función de similitud sobre secuencias de invoke para detección de plagio")
    a("- [ ] Comparar métricas de similitud Jimple vs TF-IDF (Daniel) y AST/Deckard (equipo)")
    a("- [ ] Correr sobre el dataset Java completo y reportar distribución de patrones")
    a("")
    a("---")
    a("*Reporte generado automáticamente por el pipeline Java → Jimple IR (Soot)*")

    return "\n".join(lines)

if __name__ == "__main__":
    results = load_results()
    report  = generate_report(results)
    out_path = str(REPORT_DIR / "hallazgos_soot_jimple.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ Reporte generado: {out_path}")
    print(f"   Longitud: {len(report.splitlines())} líneas")
