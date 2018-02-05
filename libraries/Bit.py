class Bit(object):
    #Bitwise operations

    @staticmethod
    def test(int_type, offset):
        #Return boolean representing state of given bit, True = set/1, False = not set/0 (cleared)
        mask = 1 << offset
        return ((int_type & mask) == (2**offset))

    @staticmethod
    def set(int_type, offset):
        #Set a given bit to 1
        mask = 1 << offset
        return (int_type | mask)

    @staticmethod
    def clear(int_type, offset):
        #Set a given bit to 0
        mask = ~(1 << offset)
        return (int_type & mask)

    @staticmethod
    def toggle(int_type, offset):
        #Toggles a given bit
        mask = 1 << offset
        return (int_type ^ mask)

    @staticmethod
    def count(int_type):
        # Returns number of bits that are set/1
        co = 0
        while(int_type):
            int_type &= int_type - 1
            co += 1
        return(co)

    @staticmethod
    def parity(int_type):
        #Returns parity, 0 if number of bits set is even, -1 if number of bits set is odd
        parity = 0
        while (int_type):
            parity = ~parity
            int_type = int_type & (int_type - 1)
        return (parity)

    @staticmethod
    def length(int_type):
        len = 0
        while (int_type):
            int_type >>= 1
            len += 1
        return (len)


    @staticmethod
    def binary(int_type):
        # Return binary representation of the integer
        return str(int_type) if int_type <= 1 else bin(int_type >> 1) + str(int_type & 1)