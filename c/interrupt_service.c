#include "interrupt_service.h"

#ifndef INTERRUPT_SERVICE_MUTATION
#define INTERRUPT_SERVICE_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffff,
    TF = 0x0100,
    IF = 0x0200,
    INTERRUPT_CLEAR = TF | IF,
    IRET_FLAGS = 0x7fd5
};

typedef struct InterruptVector {
    uint16_t code_segment;
    uint16_t instruction_pointer;
} InterruptVector;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_physical8(uint8_t *memory, const LmnRasterBus *bus,
                              uint32_t address, uint16_t flags) {
    address &= MEMORY_MASK;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_physical8(uint8_t *memory, const LmnRasterBus *bus,
                            uint32_t address, uint8_t value,
                            uint16_t flags) {
    address &= MEMORY_MASK;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical8(memory, bus, address, flags);
    uint8_t high = read_physical8(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void push_word(uint8_t *memory, LmnRegs *registers,
                      const LmnRasterBus *bus, uint16_t value,
                      uint16_t access_flags) {
    uint32_t address;
    registers->sp = (uint16_t)(registers->sp - 2u);
    address = physical(registers->ss, registers->sp);
    write_physical8(memory, bus, address, (uint8_t)value, access_flags);
    write_physical8(memory, bus, address + 1u, (uint8_t)(value >> 8),
                    access_flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         uint16_t segment, uint16_t *stack_offset,
                         uint16_t access_flags) {
    uint16_t value = read_word(memory, bus, segment, *stack_offset,
                               access_flags);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static InterruptVector read_vector(uint8_t *memory,
                                   const LmnRasterBus *bus,
                                   uint16_t interrupt_number,
                                   uint16_t access_flags) {
    InterruptVector vector;
    uint16_t offset = (uint16_t)(interrupt_number * 4u);
    /* Preserve the observed order: current IVT CS word, then IP word. */
    vector.code_segment = read_word(memory, bus, 0,
                                    (uint16_t)(offset + 2u), access_flags);
    vector.instruction_pointer = read_word(memory, bus, 0, offset,
                                           access_flags);
    return vector;
}

static uint16_t normalized_iret_flags(uint16_t flags) {
#if INTERRUPT_SERVICE_MUTATION == 3
    return flags;
#else
    return (uint16_t)((flags & IRET_FLAGS) | 2u);
#endif
}

void lmn_interrupt_return(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus) {
    uint16_t return_ss = registers->ss;
    uint16_t return_sp = registers->sp;
    uint16_t access_flags = registers->flags;
    uint16_t return_ip;
    uint16_t return_cs;
    uint16_t return_flags;
    return_ip = pop_word(memory, bus, return_ss, &return_sp, access_flags);
    return_cs = pop_word(memory, bus, return_ss, &return_sp, access_flags);
    return_flags = pop_word(memory, bus, return_ss, &return_sp,
                            access_flags);
    registers->ip = return_ip;
    registers->cs = return_cs;
    registers->flags = normalized_iret_flags(return_flags);
    registers->sp = return_sp;
}


LmnInterruptResult lmn_interrupt_invoke(uint8_t *memory,
    LmnRegs *registers, uint16_t return_cs, uint16_t resume_ip,
    const LmnInterruptService *service, const LmnRasterBus *bus) {
    LmnInterruptResult result = {LMN_INTERRUPT_RETURNED, 0};
#if INTERRUPT_SERVICE_MUTATION == 2
    uint16_t frame_ss = registers->ss;
    uint16_t frame_sp = registers->sp;
#endif
    if (!service || !service->execute ||
        service->code_segment != registers->cs ||
        service->instruction_pointer != registers->ip) {
        result.status = LMN_INTERRUPT_UNBOUND_SERVICE;
        return result;
    }
    result.service_status = service->execute(service->context, memory,
                                              registers, bus);
    if (result.service_status != 0u) {
        result.status = LMN_INTERRUPT_PROVIDER_STOP;
        return result;
    }
#if INTERRUPT_SERVICE_MUTATION == 2
    registers->ss = frame_ss;
    registers->sp = frame_sp;
#endif
    lmn_interrupt_return(memory, registers, bus);
    if (registers->cs != return_cs || registers->ip != resume_ip)
        result.status = LMN_INTERRUPT_CHANGED_IRET;
    return result;
}

LmnInterruptResult lmn_interrupt_service(uint8_t *memory,
    LmnRegs *registers, uint16_t interrupt_number, uint16_t resume_ip,
    const LmnInterruptService *service, const LmnRasterBus *bus) {
    InterruptVector vector;
    uint16_t entry_cs = registers->cs;

#if INTERRUPT_SERVICE_MUTATION == 1
    /* Mutant reads the vector before the INT frame can alter IVT aliases. */
    vector = read_vector(memory, bus, interrupt_number, registers->flags);
#endif

    registers->ip = resume_ip;
    push_word(memory, registers, bus, registers->flags, registers->flags);
    registers->flags = (uint16_t)(registers->flags &
                                  (uint16_t)~INTERRUPT_CLEAR);
    push_word(memory, registers, bus, registers->cs, registers->flags);
    push_word(memory, registers, bus, resume_ip, registers->flags);

#if INTERRUPT_SERVICE_MUTATION != 1
    vector = read_vector(memory, bus, interrupt_number, registers->flags);
#endif
    registers->cs = vector.code_segment;
    registers->ip = vector.instruction_pointer;

    return lmn_interrupt_invoke(memory, registers, entry_cs, resume_ip,
                                service, bus);
}
