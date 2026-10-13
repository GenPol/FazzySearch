from PIL import Image
import os

INPUT_FILE = "logo.jpg"
OUTPUT_FILE = "logo.ico"  # <-- совпадает с to_exe.py

SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def prepare_image(img):
    img = img.convert("RGBA")
    width, height = img.size
    side = max(width, height)

    result = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - width) // 2
    y = (side - height) // 2
    result.paste(img, (x, y), img)
    return result


def create_icon():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл не найден: {INPUT_FILE}")
        print(f"📁 Папка: {os.getcwd()}")
        return

    try:
        original = Image.open(INPUT_FILE)
        print(f"✓ Исходный файл: {original.size}")

        base = prepare_image(original)

        # Создаём слои от большего к меньшему (256 → 16)
        images = []
        for size in sorted(SIZES, reverse=True):
            layer = base.resize((size, size), Image.Resampling.LANCZOS)
            images.append(layer)
            print(f"✓ Создан слой: {size}x{size}")

        # Сохраняем: первый элемент — основной, остальные — дополнительные слои
        images[0].save(
            OUTPUT_FILE,
            format="ICO",
            sizes=[(im.width, im.height) for im in images],
            append_images=images[1:]
        )

        print("\n======================================")
        print("✅ ICO СОЗДАН")
        print("======================================")
        print(f"Файл: {OUTPUT_FILE}")
        print("Внутри находятся:")
        for size in sorted(SIZES):
            print(f"  ✓ {size}x{size}")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {type(e).__name__}\n{e}")


if __name__ == "__main__":
    create_icon()
    input("\nНажмите Enter для выхода...")