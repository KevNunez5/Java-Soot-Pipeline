/**
 * SAMPLE 02 - Programación Orientada a Objetos
 * Categoría: Clases, herencia, polimorfismo
 * Propósito: Detectar cómo se representan vtables y dispatch en LLVM IR
 */
public class Sample02_OOP {

    static abstract class Shape {
        protected String color;

        public Shape(String color) {
            this.color = color;
        }

        public abstract double area();

        public String describe() {
            return color + " shape with area " + String.format("%.2f", area());
        }
    }

    static class Circle extends Shape {
        private double radius;

        public Circle(String color, double radius) {
            super(color);
            this.radius = radius;
        }

        @Override
        public double area() {
            return Math.PI * radius * radius;
        }
    }

    static class Rectangle extends Shape {
        private double width, height;

        public Rectangle(String color, double width, double height) {
            super(color);
            this.width = width;
            this.height = height;
        }

        @Override
        public double area() {
            return width * height;
        }
    }

    public static void main(String[] args) {
        Shape[] shapes = {
            new Circle("Red", 5.0),
            new Rectangle("Blue", 4.0, 6.0),
            new Circle("Green", 3.0)
        };

        for (Shape s : shapes) {
            System.out.println(s.describe());
        }
    }
}
