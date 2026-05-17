import Foundation

enum Salsa20 {
    static func decrypt(_ data: Data, key: [UInt8], nonce: [UInt8]) -> Data {
        var output = [UInt8]()
        output.reserveCapacity(data.count)

        var counter: UInt64 = 0
        var offset = 0
        let input = [UInt8](data)

        while offset < input.count {
            let block = block(key: key, nonce: nonce, counter: counter)
            let remaining = min(64, input.count - offset)
            for index in 0..<remaining {
                output.append(input[offset + index] ^ block[index])
            }
            offset += remaining
            counter += 1
        }

        return Data(output)
    }

    private static func block(key: [UInt8], nonce: [UInt8], counter: UInt64) -> [UInt8] {
        precondition(key.count == 32)
        precondition(nonce.count == 8)

        let constants = Array("expand 32-byte k".utf8)
        var state = [UInt32](repeating: 0, count: 16)
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
        state[8] = UInt32(counter & 0xffff_ffff)
        state[9] = UInt32((counter >> 32) & 0xffff_ffff)

        var working = state
        for _ in 0..<10 {
            quarterRound(&working, 0, 4, 8, 12)
            quarterRound(&working, 5, 9, 13, 1)
            quarterRound(&working, 10, 14, 2, 6)
            quarterRound(&working, 15, 3, 7, 11)
            quarterRound(&working, 0, 1, 2, 3)
            quarterRound(&working, 5, 6, 7, 4)
            quarterRound(&working, 10, 11, 8, 9)
            quarterRound(&working, 15, 12, 13, 14)
        }

        var bytes: [UInt8] = []
        bytes.reserveCapacity(64)
        for index in 0..<16 {
            bytes.append(contentsOf: store32(working[index] &+ state[index]))
        }
        return bytes
    }

    private static func quarterRound(_ x: inout [UInt32], _ a: Int, _ b: Int, _ c: Int, _ d: Int) {
        x[b] ^= rotateLeft(x[a] &+ x[d], 7)
        x[c] ^= rotateLeft(x[b] &+ x[a], 9)
        x[d] ^= rotateLeft(x[c] &+ x[b], 13)
        x[a] ^= rotateLeft(x[d] &+ x[c], 18)
    }

    private static func rotateLeft(_ value: UInt32, _ amount: UInt32) -> UInt32 {
        (value << amount) | (value >> (32 - amount))
    }

    private static func load32(_ bytes: [UInt8], _ offset: Int) -> UInt32 {
        UInt32(bytes[offset])
            | UInt32(bytes[offset + 1]) << 8
            | UInt32(bytes[offset + 2]) << 16
            | UInt32(bytes[offset + 3]) << 24
    }

    private static func store32(_ value: UInt32) -> [UInt8] {
        [
            UInt8(value & 0xff),
            UInt8((value >> 8) & 0xff),
            UInt8((value >> 16) & 0xff),
            UInt8((value >> 24) & 0xff)
        ]
    }
}
