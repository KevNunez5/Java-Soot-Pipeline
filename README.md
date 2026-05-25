````markdown
# Java → Jimple IR Prototype with Soot

Prototipo experimental para evaluar la viabilidad de usar representaciones intermedias (IR) basadas en JVM para detección de plagio de código Java.

El objetivo de este proyecto es explorar si **Jimple**, generado mediante **Soot**, puede utilizarse como alternativa más adecuada a LLVM IR para representar programas Java a un nivel intermedio.

---

# ¿Qué es Soot?

Soot es un framework de análisis y transformación para programas Java.

A diferencia de LLVM IR, que está diseñado principalmente para lenguajes compilados nativamente como C/C++ o Rust, Soot trabaja directamente sobre el ecosistema JVM y puede transformar bytecode Java (`.class`) a **Jimple**, una representación intermedia simplificada de tres direcciones.

---

# Diferencia respecto al pipeline anterior

## Pipeline anterior (LLVM IR)

```text
.java
  │
  ▼ javac
.class (JVM bytecode)
  │
  ▼ javap
Inspección manual del bytecode JVM
  │
  ▼ llvmlite
LLVM IR (.ll)
````

Problemas encontrados:

* LLVM IR no modela naturalmente la JVM
* excepciones y garbage collector difíciles de representar
* `invokedynamic` y lambdas problemáticos
* biblioteca estándar Java no preservada naturalmente
* requería múltiples workarounds manuales

---

## Pipeline actual (Soot + Jimple)

```text
.java
  │
  ▼ javac
.class (JVM bytecode)
  │
  ▼ Soot
Jimple IR (.jimple)
```

Ventajas observadas:

* preserva herencia y polimorfismo
* soporta excepciones y lambdas
* mantiene llamadas reales a la JDK
* normaliza parcialmente variables locales
* representación mucho más natural para Java

---

# Requisitos

* Java 21+
* Python 3
* `soot.jar`

Descargar Soot:

```bash
curl -L -o soot.jar https://repo1.maven.org/maven2/org/soot-oss/soot/4.3.0/soot-4.3.0-jar-with-dependencies.jar
```

---

# Cómo ejecutar

## 1. Compilar samples Java

```bash
javac -d bytecode samples/*.java
```

---

## 2. Ejecutar pipeline

```bash
python pipeline.py
```

---

## 3. Generar reporte

```bash
python generate_report.py
```

---

# Estado del Proyecto

Este repositorio es un prototipo de validación de viabilidad, no un pipeline final de producción.

El objetivo principal es determinar si Jimple puede servir como representación intermedia útil para experimentos de detección de clones y plagio de código Java.

