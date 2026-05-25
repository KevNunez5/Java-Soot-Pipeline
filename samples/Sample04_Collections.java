/**
 * SAMPLE 04 - Colecciones y Generics
 * Categoría: ArrayList, HashMap, tipos genéricos
 * Propósito: Detectar problemas de type erasure en LLVM IR
 */
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Sample04_Collections {

    public static <T extends Comparable<T>> T findMax(List<T> list) {
        if (list.isEmpty()) throw new IllegalArgumentException("Lista vacía");
        T max = list.get(0);
        for (T item : list) {
            if (item.compareTo(max) > 0) {
                max = item;
            }
        }
        return max;
    }

    public static void main(String[] args) {
        // ArrayList con Integer
        List<Integer> numbers = new ArrayList<>();
        for (int i = 1; i <= 5; i++) numbers.add(i * 10);
        System.out.println("Lista: " + numbers);
        System.out.println("Máximo: " + findMax(numbers));

        // HashMap
        Map<String, Integer> scores = new HashMap<>();
        scores.put("Alice", 95);
        scores.put("Bob", 87);
        scores.put("Carol", 92);

        for (Map.Entry<String, Integer> entry : scores.entrySet()) {
            System.out.println(entry.getKey() + " -> " + entry.getValue());
        }

        // ArrayList de Strings
        List<String> names = new ArrayList<>();
        names.add("Zebra");
        names.add("Apple");
        names.add("Mango");
        System.out.println("Max string: " + findMax(names));
    }
}
