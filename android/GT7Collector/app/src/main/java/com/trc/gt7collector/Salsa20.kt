package com.trc.gt7collector

object Salsa20 {
    fun decrypt(data: ByteArray, key: ByteArray, nonce: ByteArray): ByteArray {
        require(key.size == 32)
        require(nonce.size == 8)
        val output = ByteArray(data.size)
        var offset = 0
        var counter = 0L
        while (offset < data.size) {
            val block = block(key, nonce, counter)
            val remaining = minOf(64, data.size - offset)
            for (index in 0 until remaining) {
                output[offset + index] = (data[offset + index].toInt() xor block[index].toInt()).toByte()
            }
            offset += remaining
            counter += 1
        }
        return output
    }

    private fun block(key: ByteArray, nonce: ByteArray, counter: Long): ByteArray {
        val constants = "expand 32-byte k".toByteArray(Charsets.US_ASCII)
        val state = IntArray(16)
        state[0] = load32(constants, 0)
        state[5] = load32(constants, 4)
        state[10] = load32(constants, 8)
        state[15] = load32(constants, 12)

        state[1] = load32(key, 0)
        state[2] = load32(key, 4)
        state[3] = load32(key, 8)
        state[4] = load32(key, 12)
        state[11] = load32(key, 16)
        state[12] = load32(key, 20)
        state[13] = load32(key, 24)
        state[14] = load32(key, 28)

        state[6] = load32(nonce, 0)
        state[7] = load32(nonce, 4)
        state[8] = (counter and 0xffff_ffffL).toInt()
        state[9] = ((counter ushr 32) and 0xffff_ffffL).toInt()

        val working = state.copyOf()
        repeat(10) {
            quarterRound(working, 0, 4, 8, 12)
            quarterRound(working, 5, 9, 13, 1)
            quarterRound(working, 10, 14, 2, 6)
            quarterRound(working, 15, 3, 7, 11)
            quarterRound(working, 0, 1, 2, 3)
            quarterRound(working, 5, 6, 7, 4)
            quarterRound(working, 10, 11, 8, 9)
            quarterRound(working, 15, 12, 13, 14)
        }

        val bytes = ByteArray(64)
        for (index in 0 until 16) {
            store32(working[index] + state[index], bytes, index * 4)
        }
        return bytes
    }

    private fun quarterRound(x: IntArray, a: Int, b: Int, c: Int, d: Int) {
        x[b] = x[b] xor rotateLeft(x[a] + x[d], 7)
        x[c] = x[c] xor rotateLeft(x[b] + x[a], 9)
        x[d] = x[d] xor rotateLeft(x[c] + x[b], 13)
        x[a] = x[a] xor rotateLeft(x[d] + x[c], 18)
    }

    private fun rotateLeft(value: Int, amount: Int): Int =
        Integer.rotateLeft(value, amount)

    private fun load32(bytes: ByteArray, offset: Int): Int =
        (bytes[offset].toInt() and 0xff) or
            ((bytes[offset + 1].toInt() and 0xff) shl 8) or
            ((bytes[offset + 2].toInt() and 0xff) shl 16) or
            ((bytes[offset + 3].toInt() and 0xff) shl 24)

    private fun store32(value: Int, target: ByteArray, offset: Int) {
        target[offset] = (value and 0xff).toByte()
        target[offset + 1] = ((value ushr 8) and 0xff).toByte()
        target[offset + 2] = ((value ushr 16) and 0xff).toByte()
        target[offset + 3] = ((value ushr 24) and 0xff).toByte()
    }
}
