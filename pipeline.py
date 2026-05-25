#!/usr/bin/env python3
"""
Pipeline: Java → Jimple IR (via Soot 4.3.0)
Investigación: Viabilidad de Soot/Jimple para detección de plagio en código Java

Flujo:
  .java → javac → .class → Soot (soot.jar) → .jimple → análisis de representación
"""

import subprocess
import os
import json
import re
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────
# CONFIGURACIÓN — rutas relativas al script
# Funciona en Windows, Mac y Linux
# ──────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.resolve()
SAMPLES_DIR  = BASE_DIR / "samples"
BYTECODE_DIR = BASE_DIR / "bytecode"
JIMPLE_DIR   = BASE_DIR / "jimple"
REPORT_DIR   = BASE_DIR / "reports"
SOOT_JAR     = BASE_DIR / "soot.jar"   # descargar de Maven Central

for _d in [BYTECODE_DIR, JIMPLE_DIR, REPORT_DIR]:
    _d.mkdir(exist_ok=True)

SAMPLES = [
    ("Sample01_Basic",       "Básico",        "variables, loops, aritmética"),
    ("Sample02_OOP",         "OOP",           "clases, herencia, polimorfismo"),
    ("Sample03_Exceptions",  "Excepciones",   "try/catch/finally"),
    ("Sample04_Collections", "Colecciones",   "generics, ArrayList, HashMap"),
    ("Sample05_Lambdas",     "Lambdas",       "lambda, Stream API, invokedynamic"),
]

# Instrucciones Jimple relevantes para análisis de plagio
JIMPLE_PATTERNS = {
    "virtualinvoke":    "Llamadas virtuales (polimorfismo)",
    "interfaceinvoke":  "Llamadas a interfaces (colecciones, streams)",
    "staticinvoke":     "Llamadas estáticas",
    "specialinvoke":    "Constructores / super calls",
    "dynamicinvoke":    "Lambdas / invokedynamic",
    "checkcast":        "Casteos de tipo (type erasure)",
    "newarray":         "Creación de arrays",
    "throw":            "Lanzamiento de excepciones",
    "catch":            "Captura de excepciones",
    "goto":             "Saltos de control de flujo",
    "if ":              "Condicionales",
    "new java.util":    "Instanciación de colecciones JDK",
}

# ──────────────────────────────────────────────
# PASO 1: Compilar .java → .class
# ──────────────────────────────────────────────
def compile_java(name):
    src  = str(SAMPLES_DIR / f"{name}.java")
    dest = str(BYTECODE_DIR)
    result = subprocess.run(
        ["javac", "-d", dest, src],
        capture_output=True, text=True
    )
    return {
        "step": "javac",
        "success": result.returncode == 0,
        "stderr": result.stderr.strip(),
    }

# ──────────────────────────────────────────────
# PASO 2: Ejecutar Soot → generar .jimple
# ──────────────────────────────────────────────
def run_soot(name):
    """
    Comando real de Soot:
      java -jar soot.jar -cp bytecode -f jimple -d jimple -pp ClassName
    Requiere soot.jar en el directorio del proyecto.
    """
    if not SOOT_JAR.exists():
        return {
            "step": "soot",
            "success": False,
            "error": f"soot.jar no encontrado en {SOOT_JAR}\n"
                     f"Descarga desde: https://repo1.maven.org/maven2/org/soot-oss/soot/4.3.0/soot-4.3.0-jar-with-dependencies.jar\n"
                     f"Renómbralo a soot.jar y colócalo en: {BASE_DIR}",
            "command": f"java -jar soot.jar -cp {BYTECODE_DIR} -f jimple -d {JIMPLE_DIR} -pp {name}",
        }

    cmd = [
        "java", "-jar", str(SOOT_JAR),
        "-cp", str(BYTECODE_DIR),
        "-f", "jimple",
        "-d", str(JIMPLE_DIR),
        "-pp",           # prepend jvm classpath
        "-allow-phantom-refs",
        name
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    success = result.returncode == 0 and (JIMPLE_DIR / f"{name}.jimple").exists()
    return {
        "step": "soot",
        "success": success,
        "stdout": result.stdout[:500],
        "stderr": result.stderr[:500],
        "command": " ".join(cmd),
    }

# ──────────────────────────────────────────────
# PASO 3: Analizar el .jimple generado
# ──────────────────────────────────────────────
def analyze_jimple(name):
    jimple_path = JIMPLE_DIR / f"{name}.jimple"
    if not jimple_path.exists():
        return {
            "step": "analyze",
            "success": False,
            "error": "Archivo .jimple no encontrado",
            "line_count": 0,
            "patterns": {},
            "invoke_types": {},
            "unique_classes": [],
            "method_count": 0,
        }

    text = jimple_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # Contar patrones Jimple
    patterns_found = {}
    for pattern, desc in JIMPLE_PATTERNS.items():
        count = sum(1 for l in lines if pattern in l)
        if count > 0:
            patterns_found[pattern] = {"count": count, "desc": desc}

    # Contar tipos de invoke (clave para análisis de plagio)
    invoke_types = {
        "virtualinvoke":   sum(1 for l in lines if "virtualinvoke" in l),
        "interfaceinvoke": sum(1 for l in lines if "interfaceinvoke" in l),
        "staticinvoke":    sum(1 for l in lines if "staticinvoke" in l),
        "specialinvoke":   sum(1 for l in lines if "specialinvoke" in l),
        "dynamicinvoke":   sum(1 for l in lines if "dynamicinvoke" in l),
    }

    # Clases referenciadas (útil para fingerprinting)
    class_refs = re.findall(r'<([\w\.\$]+):', text)
    unique_classes = sorted(set(class_refs))

    # Contar métodos definidos
    method_count = sum(1 for l in lines if re.match(r'\s+(public|private|protected|static).*\(', l))

    return {
        "step": "analyze",
        "success": True,
        "line_count": len(lines),
        "patterns": patterns_found,
        "invoke_types": {k: v for k, v in invoke_types.items() if v > 0},
        "unique_classes": unique_classes[:15],   # top 15
        "method_count": method_count,
    }

# ──────────────────────────────────────────────
# PASO 4: Comparar Jimple vs LLVM IR
# (diferencias clave para el paper)
# ──────────────────────────────────────────────
COMPARISON_TABLE = {
    "Sample01_Basic": {
        "llvm_lines": 33,
        "jimple_advantage": "Control de flujo idéntico, sin diferencias",
        "llvm_limitation": "System.out.println requiere stub externo",
        "jimple_advantage_detail": "staticinvoke preserva llamadas a Java stdlib real",
    },
    "Sample02_OOP": {
        "llvm_lines": 16,
        "jimple_advantage": "virtualinvoke preserva dispatch dinámico sin vtable manual",
        "llvm_limitation": "Requería struct Shape + function pointers manuales",
        "jimple_advantage_detail": "Herencia visible como extends en Jimple directamente",
    },
    "Sample03_Exceptions": {
        "llvm_lines": 16,
        "jimple_advantage": "catch nativo — no requiere ABI C++ ni @__cxa_throw",
        "llvm_limitation": "throw → ret -1 stub, try/catch no representado",
        "jimple_advantage_detail": "@caughtexception y catch blocks son primitivas Jimple",
    },
    "Sample04_Collections": {
        "llvm_lines": 17,
        "jimple_advantage": "java.util.ArrayList/HashMap usados directamente via interfaceinvoke",
        "llvm_limitation": "ArrayList reimplementado como struct {i8**, i32, i32}",
        "jimple_advantage_detail": "Type erasure visible pero controlado (checkcast explícito)",
    },
    "Sample05_Lambdas": {
        "llvm_lines": 13,
        "jimple_advantage": "invokedynamic → dynamicinvoke + lambda$N sintéticos — representable",
        "llvm_limitation": "invokedynamic sin equivalente en LLVM IR — limitación crítica",
        "jimple_advantage_detail": "Stream API preservada como cadena de interfaceinvoke reales",
    },
}

# ──────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ──────────────────────────────────────────────
def run_pipeline():
    print("=" * 65)
    print("  PIPELINE: Java → Jimple IR (Soot)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Directorio: {BASE_DIR}")
    soot_status = "✅ encontrado" if SOOT_JAR.exists() else "⚠️  NO encontrado (ver instrucciones abajo)"
    print(f"  soot.jar: {soot_status}")
    print("=" * 65)

    if not SOOT_JAR.exists():
        print("\n  ⚠️  SOOT.JAR REQUERIDO")
        print("  Descarga con este comando:")
        print("  curl -L -o soot.jar https://repo1.maven.org/maven2/org/soot-oss/soot/4.3.0/soot-4.3.0-jar-with-dependencies.jar")
        print("  (o descarga manualmente y renómbralo a soot.jar)")
        print()

    all_results = []

    for name, category, desc in SAMPLES:
        print(f"\n▶ {name} [{category}] — {desc}")
        r = {"name": name, "category": category, "description": desc}

        # Paso 1: javac
        step1 = compile_java(name)
        r["javac"] = step1
        print(f"  {'✅' if step1['success'] else '❌'} javac: {'OK' if step1['success'] else step1['stderr']}")

        # Paso 2: Soot → Jimple
        step2 = run_soot(name)
        r["soot"] = step2
        if step2["success"]:
            print(f"  ✅ Soot → Jimple: OK")
        elif "soot.jar no encontrado" in step2.get("error", ""):
            print(f"  ⏳ Soot: pendiente de soot.jar")
            print(f"     Comando a correr: {step2['command']}")
        else:
            print(f"  ❌ Soot: {step2.get('error', step2.get('stderr', ''))[:120]}")

        # Paso 3: Analizar Jimple (funciona con archivos de referencia)
        step3 = analyze_jimple(name)
        r["analysis"] = step3
        if step3["success"]:
            invoke_summary = ", ".join(f"{k}:{v}" for k, v in step3["invoke_types"].items())
            print(f"  📊 Jimple: {step3['line_count']} líneas | invokes: [{invoke_summary}]")
            if "dynamicinvoke" in step3["invoke_types"]:
                print(f"     ✅ dynamicinvoke detectado — lambdas representadas (ventaja vs LLVM IR)")
        else:
            print(f"  📊 Jimple: análisis pendiente (necesita soot.jar para generar .jimple)")

        # Paso 4: Comparación vs LLVM IR
        comp = COMPARISON_TABLE.get(name, {})
        r["vs_llvm"] = comp
        if comp:
            print(f"  🔄 vs LLVM IR: {comp.get('jimple_advantage', '')}")

        all_results.append(r)

    # Guardar JSON
    report_path = str(REPORT_DIR / "soot_pipeline_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'='*65}")
    print("  RESUMEN")
    print(f"{'='*65}")
    ok_javac = sum(1 for r in all_results if r["javac"]["success"])
    ok_soot  = sum(1 for r in all_results if r["soot"]["success"])
    ok_anal  = sum(1 for r in all_results if r["analysis"]["success"])
    print(f"  Samples procesados : {len(all_results)}")
    print(f"  Compilación javac  : {ok_javac}/{len(all_results)} exitosos")
    print(f"  Soot → Jimple      : {ok_soot}/{len(all_results)} {'✅' if ok_soot == len(all_results) else '⏳ (requiere soot.jar)'}")
    print(f"  Análisis Jimple    : {ok_anal}/{len(all_results)} exitosos")
    print(f"  Reporte guardado   : {report_path}")
    if not SOOT_JAR.exists():
        print()
        print("  📥 Para completar el pipeline, descarga soot.jar:")
        print("     curl -L -o soot.jar https://repo1.maven.org/maven2/org/soot-oss/soot/4.3.0/soot-4.3.0-jar-with-dependencies.jar")
        print("     Luego vuelve a correr: python pipeline.py")
    print(f"{'='*65}\n")

    return all_results

if __name__ == "__main__":
    run_pipeline()
