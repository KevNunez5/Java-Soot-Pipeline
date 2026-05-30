#!/usr/bin/env python3
"""
jimple_xgboost_pipeline.py
Pipeline: Java → Jimple IR (Soot 4.3.0) → XGBoost Classifier
Detección multiclase de clones de código Java

Estructura compatible con el repo del equipo:
  - Misma función load_jsonl() que baseline y AST pipelines
  - Mismos splits: train_balanced.jsonl / valid_balanced.jsonl / test_balanced.jsonl
  - Mismo clasificador XGBClassifier con SEED=42
  - Output en results/jimple_xgboost/ (compatible con estructura de resultados)

Autor: Pipeline Jimple — Línea de investigación IR
"""

import json
import os
import re
import subprocess
import tempfile
import warnings
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.metrics import classification_report, accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN GLOBAL
# ──────────────────────────────────────────────────────────────
SEED = 42  # Igual que todos los otros pipelines del equipo

# Rutas — compatibles con la estructura del repo del equipo
# Cuando el script esté en dataset_clones_java/, data_dir apunta a model_ready_balanced/
SCRIPT_DIR  = Path(__file__).resolve().parent
DATA_DIR    = SCRIPT_DIR / "model_ready_balanced"   # repo del equipo
SOOT_JAR    = SCRIPT_DIR / "soot.jar"               # debe estar junto al script
RESULTS_DIR = SCRIPT_DIR / "results" / "jimple_xgboost"

# Rutas de trabajo temporal
TEMP_DIR    = SCRIPT_DIR / "_jimple_temp"           # .java y .class temporales
JIMPLE_DIR  = SCRIPT_DIR / "_jimple_output"         # archivos .jimple generados

# Si estás corriendo en el repo AISLADO (java_soot_pipeline),
# descomenta estas líneas en lugar de las anteriores:
# DATA_DIR = SCRIPT_DIR / "data"   # pon aquí tus jsonl de prueba

# ──────────────────────────────────────────────────────────────
# FEATURES JIMPLE — 18 instrucciones clave para detección de plagio
# Seleccionadas porque capturan la lógica de ejecución independiente
# del estilo de escritura (resistentes a renombrado y reformateo)
# ──────────────────────────────────────────────────────────────
JIMPLE_FEATURES = [
    "virtualinvoke",    # llamadas polimórficas (herencia)
    "interfaceinvoke",  # llamadas a interfaces (colecciones, streams)
    "staticinvoke",     # llamadas estáticas
    "specialinvoke",    # constructores y super calls
    "dynamicinvoke",    # lambdas e invokedynamic
    "checkcast",        # casteos de tipo (type erasure)
    "instanceof",       # verificación de tipo en runtime
    "newarray",         # creación de arrays
    "new ",             # instanciación de objetos
    "throw",            # lanzamiento de excepciones
    "catch",            # captura de excepciones
    "goto",             # saltos incondicionales (loops)
    "if ",              # condicionales
    "return",           # puntos de retorno
    "= null",           # asignaciones nulas
    "lengthof",         # acceso a longitud de array
    "= (int)",          # casteos numéricos
    "= (double)",       # casteos a double
]
N_FEATURES = len(JIMPLE_FEATURES)  # 18

# ──────────────────────────────────────────────────────────────
# PASO 1: Carga de datos — idéntica al baseline y AST pipelines
# ──────────────────────────────────────────────────────────────
def load_jsonl(path: str) -> list:
    """
    Carga registros JSONL con func1, func2, clone_type.
    Copia exacta de la función en baseline_xgboost_pipeline.py
    para garantizar compatibilidad total con el repo del equipo.
    """
    required_fields = {"func1", "func2", "clone_type"}
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.warn(f"{path}:{line_number}: JSON inválido omitido ({exc})")
                continue
            missing = required_fields - set(obj)
            if missing:
                warnings.warn(f"{path}:{line_number}: campos faltantes omitidos: {missing}")
                continue
            records.append({
                "func1": obj["func1"],
                "func2": obj["func2"],
                "clone_type": obj["clone_type"],
            })
    return records

# ──────────────────────────────────────────────────────────────
# PASO 2: Preparación del código Java para Soot
# El dataset contiene SOLO el cuerpo del método (sin firma),
# igual que en el pipeline AST — necesitamos envolver en clase
# ──────────────────────────────────────────────────────────────
def wrap_for_soot(method_body: str, class_name: str = "SootInput") -> str:
    """
    Envuelve el cuerpo de un método en una clase Java válida para Soot.
    El dataset contiene solo el cuerpo — igual que en ast_xgboost_pipeline.py.
    
    Soot necesita una clase completa con método firmado para generar Jimple.
    """
    body = (method_body or "").strip()
    return (
        f"public class {class_name} {{\n"
        f"    public static void method() {{\n"
        f"        {body}\n"
        f"    }}\n"
        f"}}\n"
    )

# ──────────────────────────────────────────────────────────────
# PASO 3: Compilar .java → .class con javac
# ──────────────────────────────────────────────────────────────
def compile_to_bytecode(java_code: str, class_name: str, out_dir: Path) -> bool:
    """Escribe el .java y lo compila a .class. Retorna True si exitoso."""
    java_path = out_dir / f"{class_name}.java"
    java_path.write_text(java_code, encoding="utf-8")
    result = subprocess.run(
        ["javac", "-d", str(out_dir), str(java_path)],
        capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0

# ──────────────────────────────────────────────────────────────
# PASO 4: Soot → .jimple
# ──────────────────────────────────────────────────────────────
def run_soot(class_name: str, bytecode_dir: Path, jimple_out_dir: Path) -> bool:
    """
    Ejecuta Soot sobre la clase compilada y genera el archivo .jimple.
    Retorna True si el archivo .jimple fue generado exitosamente.
    """
    if not SOOT_JAR.exists():
        raise FileNotFoundError(
            f"soot.jar no encontrado en {SOOT_JAR}\n"
            f"Descarga: curl -L -o soot.jar "
            f"https://repo1.maven.org/maven2/org/soot-oss/soot/4.3.0/"
            f"soot-4.3.0-jar-with-dependencies.jar"
        )
    cmd = [
        "java", "-jar", str(SOOT_JAR),
        "-cp", str(bytecode_dir),
        "-f", "jimple",
        "-d", str(jimple_out_dir),
        "-pp",
        "-allow-phantom-refs",
        class_name
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0 and (jimple_out_dir / f"{class_name}.jimple").exists()

# ──────────────────────────────────────────────────────────────
# PASO 5: Extraer vector de features desde el .jimple
# ──────────────────────────────────────────────────────────────
def extract_features_from_jimple(jimple_path: Path) -> np.ndarray:
    """
    Lee el archivo .jimple y cuenta cada instrucción de JIMPLE_FEATURES.
    Devuelve un vector numpy de shape (N_FEATURES,) con conteos normalizados.
    """
    try:
        text = jimple_path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        total_lines = max(len(lines), 1)
        vec = np.array(
            [sum(1 for l in lines if feat in l) / total_lines
             for feat in JIMPLE_FEATURES],
            dtype=np.float32
        )
        return vec
    except Exception:
        return np.zeros(N_FEATURES, dtype=np.float32)

# ──────────────────────────────────────────────────────────────
# PASO 6: Pipeline completo por método individual
# ──────────────────────────────────────────────────────────────
def method_to_jimple_vector(method_body: str, idx: int, suffix: str,
                             work_dir: Path) -> tuple:
    """
    Toma el cuerpo de un método Java, lo compila con javac,
    lo procesa con Soot y devuelve (vector_numpy, éxito_bool).
    """
    class_name = f"SootInput_{idx}_{suffix}"
    java_code   = wrap_for_soot(method_body, class_name)

    compiled = compile_to_bytecode(java_code, class_name, work_dir)
    if not compiled:
        return np.zeros(N_FEATURES, dtype=np.float32), False

    jimple_out = work_dir / "jimple"
    jimple_out.mkdir(exist_ok=True)
    soot_ok = run_soot(class_name, work_dir, jimple_out)
    if not soot_ok:
        return np.zeros(N_FEATURES, dtype=np.float32), False

    vec = extract_features_from_jimple(jimple_out / f"{class_name}.jimple")
    return vec, True

# ──────────────────────────────────────────────────────────────
# PASO 7: Construir matriz de features para un split completo
# Mismo patrón simétrico que TF-IDF y AST pipelines del equipo
# ──────────────────────────────────────────────────────────────
def extract_jimple_pair_features(records: list, split_name: str) -> tuple:
    """
    Para cada par (func1, func2) genera el vector simétrico Jimple:
      X_pair = [|v1 - v2|, v1 ⊙ v2, cosine_sim(v1, v2)]
    Shape final: (n_pairs, N_FEATURES*2 + 1) = (n_pairs, 37)

    Mismo diseño que extract_tfidf_features() y extract_ast_pair_features()
    del repo del equipo para garantizar comparabilidad directa.
    """
    n = len(records)
    # 18 abs_diff + 18 product + 1 cosine = 37 features por par
    X = np.zeros((n, N_FEATURES * 2 + 1), dtype=np.float32)
    y = []
    success_count = 0

    print(f"  Procesando {n} pares [{split_name}]...")

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        (work_dir / "jimple").mkdir()

        for i, rec in enumerate(records):
            if i % 500 == 0:
                print(f"    [{split_name}] {i}/{n} pares procesados "
                      f"({success_count} exitosos)...")

            v1, ok1 = method_to_jimple_vector(rec["func1"], i, "f1", work_dir)
            v2, ok2 = method_to_jimple_vector(rec["func2"], i, "f2", work_dir)

            if ok1 and ok2:
                success_count += 1

            # Vector simétrico — igual que TF-IDF y AST del equipo
            abs_diff   = np.abs(v1 - v2)
            product    = v1 * v2
            norm1      = np.linalg.norm(v1) + 1e-9
            norm2      = np.linalg.norm(v2) + 1e-9
            cosine_sim = np.dot(v1, v2) / (norm1 * norm2)

            X[i] = np.concatenate([abs_diff, product, [cosine_sim]])
            y.append(rec["clone_type"])

    rate = success_count / n * 100
    print(f"  ✅ [{split_name}] Tasa de éxito Soot: {rate:.2f}% ({success_count}/{n})")
    return X, y, rate

# ──────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ──────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  PIPELINE: Jimple IR + XGBoost")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Directorio: {SCRIPT_DIR}")
    print(f"  soot.jar: {'✅ encontrado' if SOOT_JAR.exists() else '❌ NO encontrado'}")
    print(f"  data_dir: {DATA_DIR}")
    print("=" * 65)

    # Verificar soot.jar antes de empezar
    if not SOOT_JAR.exists():
        print("\n❌ ERROR: soot.jar requerido.")
        print("   Descarga con:")
        print("   curl -L -o soot.jar https://repo1.maven.org/maven2/org/soot-oss/"
              "soot/4.3.0/soot-4.3.0-jar-with-dependencies.jar")
        return

    # Verificar data
    for fname in ["train_balanced.jsonl", "valid_balanced.jsonl", "test_balanced.jsonl"]:
        if not (DATA_DIR / fname).exists():
            print(f"\n❌ ERROR: No se encontró {DATA_DIR / fname}")
            print("   Asegúrate de que model_ready_balanced/ está en el mismo directorio que este script.")
            return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Cargar datos (idéntico a baseline y AST pipelines) ──
    print("\n📂 Cargando datos balanceados...")
    train_data = load_jsonl(str(DATA_DIR / "train_balanced.jsonl"))
    valid_data = load_jsonl(str(DATA_DIR / "valid_balanced.jsonl"))
    test_data  = load_jsonl(str(DATA_DIR / "test_balanced.jsonl"))
    print(f"   Train: {len(train_data)} | Valid: {len(valid_data)} | Test: {len(test_data)}")

    # ── Extraer features Jimple ──
    print("\n🔧 Extrayendo features Jimple (esto toma varios minutos)...")
    X_train, y_train, rate_train = extract_jimple_pair_features(train_data, "Train")
    X_valid, y_valid, rate_valid = extract_jimple_pair_features(valid_data, "Valid")
    X_test,  y_test,  rate_test  = extract_jimple_pair_features(test_data,  "Test")

    print(f"\n   Shape Train : {X_train.shape}")
    print(f"   Shape Valid : {X_valid.shape}")
    print(f"   Shape Test  : {X_test.shape}")
    print(f"   Features por par: {N_FEATURES*2+1} "
          f"({N_FEATURES} abs_diff + {N_FEATURES} product + 1 cosine)")

    # ── Encoding de etiquetas ──
    le = LabelEncoder()
    le.fit(y_train)
    y_train_enc = le.transform(y_train)
    y_valid_enc = le.transform(y_valid)
    y_test_enc  = le.transform(y_test)

    # ── Entrenar XGBoost (configuración idéntica al equipo) ──
    print("\n🌳 Entrenando XGBoost...")
    clf = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        random_state=SEED,
        eval_metric="mlogloss",
        early_stopping_rounds=15,
        tree_method="hist",
        n_jobs=-1
    )
    clf.fit(
        X_train, y_train_enc,
        eval_set=[(X_valid, y_valid_enc)],
        verbose=50
    )
    best_round = clf.best_iteration
    print(f"   Mejor iteración: {best_round}")

    # ── Evaluación en Test ──
    print("\n📊 Evaluando en Test...")
    y_pred_enc = clf.predict(X_test)
    y_pred     = le.inverse_transform(y_pred_enc)

    accuracy   = accuracy_score(y_test, y_pred) * 100
    macro_f1   = f1_score(y_test, y_pred, average="macro") * 100
    weighted_f1= f1_score(y_test, y_pred, average="weighted") * 100

    report = classification_report(y_test, y_pred, digits=4)

    # ── Mostrar resultados ──
    print("\n" + "=" * 65)
    print("  RESULTADOS — Jimple + XGBoost")
    print("=" * 65)
    print(f"  Accuracy    : {accuracy:.2f}%")
    print(f"  Macro F1    : {macro_f1:.2f}%")
    print(f"  Weighted F1 : {weighted_f1:.2f}%")
    print(f"\n  Tasas de éxito Soot:")
    print(f"    Train : {rate_train:.2f}%")
    print(f"    Valid : {rate_valid:.2f}%")
    print(f"    Test  : {rate_test:.2f}%")
    print(f"\n{report}")

    # ── Guardar resultados ──
    results = {
        "timestamp": datetime.now().isoformat(),
        "model": "Jimple + XGBoost",
        "features": N_FEATURES * 2 + 1,
        "jimple_features_list": JIMPLE_FEATURES,
        "best_xgb_iteration": best_round,
        "soot_success_rates": {
            "train": rate_train,
            "valid": rate_valid,
            "test":  rate_test
        },
        "metrics": {
            "accuracy":    round(accuracy, 4),
            "macro_f1":    round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
        },
        "classification_report": report,
        "splits": {
            "train": len(train_data),
            "valid": len(valid_data),
            "test":  len(test_data)
        }
    }

    results_path = RESULTS_DIR / "jimple_xgboost_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Resultados guardados en: {results_path}")
    print("=" * 65)

    # ── Tabla comparativa (para el paper) ──
    print("\n📋 TABLA COMPARATIVA (para el artículo):")
    print(f"{'Modelo':<30} {'Accuracy':>10} {'Macro F1':>10} {'Features':>10}")
    print("-" * 65)
    print(f"{'TF-IDF + XGBoost':<30} {'84.54%':>10} {'87.30%':>10} {'2,001':>10}")
    print(f"{'AST + XGBoost':<30} {'77.74%':>10} {'76.10%':>10} {'58':>10}")
    print(f"{'TF-IDF + AST (Híbrido)':<30} {'92.44%':>10} {'93.82%':>10} {'2,059':>10}")
    print(f"{'Jimple + XGBoost':<30} {accuracy:>9.2f}% {macro_f1:>9.2f}% "
          f"{N_FEATURES*2+1:>10,}")
    print("=" * 65)

if __name__ == "__main__":
    main()
