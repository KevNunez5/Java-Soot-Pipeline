/**
 * SAMPLE 05 - Lambdas y Streams
 * Categoría: Lambda expressions, Stream API, functional interfaces
 * Propósito: Caso extremo — documentar fallos esperados en IR por invokedynamic
 */
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class Sample05_Lambdas {

    @FunctionalInterface
    interface MathOperation {
        int operate(int a, int b);
    }

    public static int apply(int a, int b, MathOperation op) {
        return op.operate(a, b);
    }

    public static void main(String[] args) {
        // Lambdas como functional interfaces
        MathOperation add = (a, b) -> a + b;
        MathOperation multiply = (a, b) -> a * b;

        System.out.println("Suma: " + apply(5, 3, add));
        System.out.println("Multiplicación: " + apply(5, 3, multiply));
        System.out.println("Lambda inline: " + apply(10, 2, (a, b) -> a - b));

        // Stream API
        List<Integer> numbers = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);

        List<Integer> evenSquares = numbers.stream()
            .filter(n -> n % 2 == 0)
            .map(n -> n * n)
            .collect(Collectors.toList());

        System.out.println("Cuadrados pares: " + evenSquares);

        int sum = numbers.stream()
            .reduce(0, Integer::sum);
        System.out.println("Suma total: " + sum);
    }
}
