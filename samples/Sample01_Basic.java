/**
 * SAMPLE 01 - Java Básico
 * Categoría: Variables, loops, aritmética
 * Propósito: Baseline del pipeline — debe transformarse sin problemas
 */
public class Sample01_Basic {

    public static int factorial(int n) {
        int result = 1;
        for (int i = 2; i <= n; i++) {
            result *= i;
        }
        return result;
    }

    public static double sumArray(int[] arr) {
        double sum = 0.0;
        for (int i = 0; i < arr.length; i++) {
            sum += arr[i];
        }
        return sum;
    }

    public static void main(String[] args) {
        // Aritmética básica
        int a = 10, b = 3;
        System.out.println("Suma: " + (a + b));
        System.out.println("Producto: " + (a * b));
        System.out.println("División entera: " + (a / b));
        System.out.println("Módulo: " + (a % b));

        // Loop y función
        System.out.println("Factorial de 5: " + factorial(5));

        // Array
        int[] nums = {1, 2, 3, 4, 5};
        System.out.println("Suma del array: " + sumArray(nums));
    }
}
