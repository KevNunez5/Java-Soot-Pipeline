/**
 * SAMPLE 03 - Manejo de Excepciones
 * Categoría: try/catch/finally, excepciones custom
 * Propósito: Documentar cómo el manejo de stack de excepciones se traduce a IR
 */
public class Sample03_Exceptions {

    static class InvalidAgeException extends RuntimeException {
        public InvalidAgeException(String msg) {
            super(msg);
        }
    }

    public static int divide(int a, int b) {
        if (b == 0) {
            throw new ArithmeticException("División por cero no permitida");
        }
        return a / b;
    }

    public static void validateAge(int age) {
        if (age < 0 || age > 150) {
            throw new InvalidAgeException("Edad inválida: " + age);
        }
        System.out.println("Edad válida: " + age);
    }

    public static void main(String[] args) {
        // try/catch estándar
        try {
            int result = divide(10, 2);
            System.out.println("10 / 2 = " + result);
            int bad = divide(5, 0);
        } catch (ArithmeticException e) {
            System.out.println("Capturado: " + e.getMessage());
        } finally {
            System.out.println("Bloque finally ejecutado");
        }

        // Excepción personalizada
        try {
            validateAge(25);
            validateAge(-5);
        } catch (InvalidAgeException e) {
            System.out.println("Excepción custom: " + e.getMessage());
        }
    }
}
