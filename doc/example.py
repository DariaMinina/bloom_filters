class BloomFilter:
    def __init__(self, size, hash_functions):
        self.size = size
        self.bit_array = [False] * size
        self.hash_functions = hash_functions

    def add(self, item):
        for seed in self.hash_functions:
            index = hash(item) % self.size
            self.bit_array[index] = True

    def lookup(self, item):
        for seed in self.hash_functions:
            index = hash(item) % self.size
            if not self.bit_array[index]:
                return False
        return True

# Создаем Bloom-filter с размером 100 и 3 хеш-функциями
bf = BloomFilter(size=100, hash_functions=[hash, lambda x: hash(x) * 31, lambda x: hash(x) * 37])

# Добавляем элементы
bf.add("apple")
bf.add("banana")

# Проверяем наличие элементов
print(bf.lookup("apple"))  # Вернет True
print(bf.lookup("banana"))  # Вернет True
print(bf.lookup("cherry"))  # Вернет False