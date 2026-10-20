#include "game_loop.h"
#include "lemmings_sym.h"
#include "resource_retry.h"
#include <setjmp.h>
#ifndef GAME_LOOP_MUTATION
#define GAME_LOOP_MUTATION 0
#endif

/* The legacy typed retry callback can return only AX/BX/BP/FLAGS. Its callers
   pop the actual near CALL word and restore SI/DI/DS/ES/CX/DX from live RAM,
   then re-probe (1D20 -> 1CEE) or reload (1BA7 -> 1B79). Run the UI on that
   same state; leave the caller's POP transport to those maintained cores.
   Only a stopped UI or changed return escapes this void callback, which has
   no status/full-state result with which to unwind its resource parents.
   The setjmp lives in invoke_start; the changed packet lives in its caller,
   so no modified automatic local is read after longjmp. */
typedef struct StartBoundary {
    jmp_buf escape;
    uint8_t *memory;
    const LmnRegs *input;
    LmnRegs stopped;
    uint16_t game_ds;
    LmnLevelStartEntry entry;
    const LmnForegroundPoll *poll;
    const LmnDatFileServices *files;
    const LmnGameLoopServices *loop;
    uint16_t stop_status,core_status,child_status,service_status;
    LmnLevelStartServices services;
    LmnLevelStartResult result;
} StartBoundary;
static void retry_open(void *context,uint8_t *memory,uint16_t segment,uint16_t filename,
    uint16_t flags,LmnDatFileServiceResult *out) {
    StartBoundary *s=context;
    s->files->open_readonly(s->files->context,memory,segment,filename,flags,out);
}
static void retry_attributes(void *context,uint8_t *memory,uint16_t segment,uint16_t filename,
    uint16_t flags,LmnDatFileServiceResult *out) {
    StartBoundary *s=context;
    s->files->attributes(s->files->context,memory,segment,filename,flags,out);
}
static uint16_t retry_word(uint8_t *memory,uint16_t segment,uint16_t offset,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=(((uint32_t)segment<<4)+offset)&0xFFFFFu;
    uint8_t low=bus&&bus->read_byte?bus->read_byte(bus->context,memory,at,flags):memory[at];
    at=(at+1u)&0xFFFFFu;
    uint8_t high=bus&&bus->read_byte?bus->read_byte(bus->context,memory,at,flags):memory[at];
    return (uint16_t)(low|((uint16_t)high<<8));
}
static void retry_screen(void *context,uint8_t *memory,const LmnDatFileCall *call,LmnDatRetryResult *out) {
    StartBoundary *s=context;const LmnGameLoopServices *loop=s->loop;
    s->stopped=(LmnRegs){call->value,call->handle,call->count,call->filename_offset,
        call->source_cursor,call->output_cursor,call->base_cursor,call->stack_offset,
        s->input->cs,call->segment,call->extra_segment,call->stack_segment,CS_ShowResourceRetryScreen,call->flags};
    s->stop_status=LMN_GAME_LOOP_UNBOUND_SERVICE;
    if(!loop->video||!loop->video->set_mode||!s->poll||!s->poll->poll)longjmp(s->escape,1);
    /* Reading the entry word here is control-flow validation, not an emulated
       bus read. The actual RET below reads its then-live bytes through the bus. */
    uint16_t expected=retry_word(memory,call->stack_segment,call->stack_offset,call->flags,0);
    if(expected!=CS_DatAfterFileRetry&&expected!=CS_DatAfterResourceRetry) {
        s->core_status=LMN_RESOURCE_RETRY_CHANGED_RETURN;
        s->stop_status=LMN_GAME_LOOP_UNSUPPORTED_TRANSFER;longjmp(s->escape,1);
    }
    LmnVideoRestoreState input={call->value,call->handle,call->count,call->filename_offset,
        call->source_cursor,call->output_cursor,call->base_cursor,call->segment,
        call->extra_segment,call->stack_segment,call->stack_offset,call->flags};
    LmnResourceRetryResult result=lmn_resource_retry_screen_core(memory,s->input->cs,
        s->game_ds,&input,loop->video,loop->bus,loop->ports,s->poll);
    LmnVideoRestoreState *v=&result.state;LmnRegs *r=&s->stopped;
    *r=(LmnRegs){v->value,v->base_value,v->count,v->argument,v->source_cursor,
        v->output_cursor,v->frame_cursor,v->stack_offset,result.code_segment,
        v->data_segment,v->extra_segment,v->stack_segment,result.continuation,v->flags};
    s->core_status=(uint16_t)result.status;s->child_status=result.child_status;
    s->service_status=result.status==LMN_RESOURCE_RETRY_POLL_STOP?result.child_status:0;
    s->stop_status=result.status==LMN_RESOURCE_RETRY_POLL_STOP?LMN_GAME_LOOP_CORE_STOP:
        result.status==LMN_RESOURCE_RETRY_WAITING?LMN_GAME_LOOP_UNBOUND_SERVICE:
        result.status==LMN_RESOURCE_RETRY_CHANGED_RETURN?LMN_GAME_LOOP_UNSUPPORTED_TRANSFER:
        LMN_GAME_LOOP_RESOURCE_RETRY;
    if(result.status!=LMN_RESOURCE_RETRY_READY)longjmp(s->escape,1);
    r->ip=retry_word(memory,r->ss,r->sp,r->flags,loop->bus);r->sp=(uint16_t)(r->sp+2u);
    if(r->ip!=expected||r->cs!=s->input->cs||r->ss!=call->stack_segment||
       r->sp!=(uint16_t)(call->stack_offset+2u)) {
        s->core_status=LMN_RESOURCE_RETRY_CHANGED_RETURN;
        s->stop_status=LMN_GAME_LOOP_UNSUPPORTED_TRANSFER;longjmp(s->escape,1);
    }
    *out=(LmnDatRetryResult){r->ax,r->bx,r->bp,r->flags};
}
static int invoke_start(StartBoundary *s) {
    if(setjmp(s->escape))return 0;
    s->result=lmn_start_selected_level_polled(s->memory,s->input,s->game_ds,s->entry,&s->services,s->poll);
    return 1;
}
static int start_level(StartBoundary *s,const LmnLevelStartServices *services) {
    if(!services) {
        s->result=lmn_start_selected_level_polled(s->memory,s->input,s->game_ds,s->entry,0,s->poll);
        return 1;
    }
    s->services=*services;
    const LmnResourceSelectionFullServices *full=services->resources;
    const LmnResourceSelectionServices *selection=full?full->selection:0;
    s->files=selection?selection->files:0;
    if(!s->files||!s->files->open_readonly||!s->files->attributes)return invoke_start(s);
    LmnDatFileServices files={s,retry_open,retry_attributes,retry_screen};
    LmnResourceSelectionServices selected=*selection;selected.files=&files;
    LmnResourceSelectionFullServices bound=*full;bound.selection=&selected;
    s->services.resources=&bound;
    return invoke_start(s);
}
LmnGameLoopResult lmn_game_loop_core(uint8_t *memory,const LmnRegs *registers,
    const LmnGameLoopServices *s) {
    LmnGameLoopResult out={*registers,0,0,0,0,0};LmnRegs *r=&out.registers;
    for(;;) {
        out.core_entry=r->ip;
        if(!s){out.status=LMN_GAME_LOOP_UNBOUND_SERVICE;return out;}
        if(r->cs!=s->code_segment){out.status=LMN_GAME_LOOP_UNSUPPORTED_TRANSFER;return out;}
        if(r->ip==0x04D0){out.status=LMN_GAME_LOOP_FATAL_CLEANUP;return out;}
        /* A raw retry entry has no suspended DAT parent to resume after RET. */
        if(r->ip==0x4B1C){out.status=LMN_GAME_LOOP_RESOURCE_RETRY;return out;}
        if(r->ip==CS_CleanupTerminateInterrupt||r->ip==CS_CleanupAfterTerminate) {
            out.status=LMN_GAME_LOOP_DOS_EXIT;return out;
        }
        /* A connected run requires its sole asynchronous/cancellation seam.
           Legacy cores retain their NULL-poll contracts; an unbound driver
           must not enter a foreground wait it cannot service or cancel. */
        switch(r->ip) {
        case CS_EnterMainMenu:case CS_MenuRefresh4401:case CS_MainMenuCodeTransition:
        case CS_ShowInputSelection4A01:case CS_MainMenuStartLevel:case CS_LoadAndStartSelectedLevel:
        case CS_EnterLoadedLevelGame:case CS_LevelResultScreen:
            if(!s->poll||!s->poll->poll){out.status=LMN_GAME_LOOP_UNBOUND_SERVICE;return out;}
            break;
        default:break;
        }
        if(s->observe)s->observe(s->observer_context,memory,r);
        switch(r->ip) {
        case CS_EnterMainMenu:case CS_MenuRefresh4401:case CS_MainMenuCodeTransition: {
            LmnMainMenuResult c=r->ip==CS_EnterMainMenu?
                lmn_enter_main_menu_polled(memory,r,s->game_data_segment,s->video,s->dos,s->ports,s->bus,s->poll):
                r->ip==CS_MainMenuCodeTransition?
                lmn_show_code_entry_polled(memory,r,s->game_data_segment,s->ports,s->bus,s->poll):
                lmn_run_main_menu_polled(memory,r,s->game_data_segment,LMN_MAIN_MENU_REFRESH,s->ports,s->bus,s->poll);
            *r=c.registers;out.core_status=c.status;out.child_status=c.child_status;
            if(GAME_LOOP_MUTATION==1&&r->ip==CS_MainMenuStartLevel)r->ip=CS_MenuRefresh4401;
            break;
        }
        case CS_ShowInputSelection4A01: {
            LmnKeyboardResult c=lmn_show_input_selection_polled(memory,r,s->ports,s->bus,s->poll);
            *r=c.registers;out.core_status=c.status;out.child_status=c.child_status;out.service_status=c.service_status;break;
        }
        case CS_MainMenuStartLevel:case CS_LoadAndStartSelectedLevel: {
            StartBoundary boundary={0};boundary.memory=memory;boundary.input=r;boundary.game_ds=s->game_data_segment;
            boundary.entry=r->ip==CS_MainMenuStartLevel||GAME_LOOP_MUTATION==3?LMN_LEVEL_START_FROM_MENU:LMN_LEVEL_START_COMMON;
            boundary.poll=s->poll;boundary.loop=s;
            if(!start_level(&boundary,s->start)) {
                *r=boundary.stopped;out.status=boundary.stop_status;
                out.core_status=boundary.core_status;out.child_status=boundary.child_status;
                out.service_status=boundary.service_status;return out;
            }
            LmnLevelStartResult c=boundary.result;
            *r=c.registers;out.core_status=c.status;out.child_status=c.child_status;out.service_status=c.detail;break;
        }
        case CS_EnterLoadedLevelGame: {
            if(!s->session){out.status=LMN_GAME_LOOP_UNBOUND_SERVICE;return out;}
            LmnGameSessionServices binding=*s->session;
            LmnGameInitializeServices init;
            LmnGameFrameServices frame;
            if(binding.initialize){init=*binding.initialize;init.foreground=s->poll;binding.initialize=&init;}
            if(binding.frame){frame=*binding.frame;frame.poll=s->poll;binding.frame=&frame;}
            LmnGameSessionResult c=lmn_game_session_core(memory,r,&binding);
            *r=c.registers;out.core_status=c.status;out.child_status=c.child_status;out.service_status=c.service_status;break;
        }
        case CS_LevelResultScreen: {
            if(!s->result){out.status=LMN_GAME_LOOP_UNBOUND_SERVICE;return out;}
            LmnLevelResultServices binding=*s->result;binding.poll=s->poll;
            LmnLevelResultResult c=lmn_level_result_core(memory,r,&binding);
            *r=c.registers;out.core_status=(c.status==LMN_LEVEL_RESULT_MAIN_MENU||c.status==LMN_LEVEL_RESULT_START_LEVEL)?0:c.status;
            out.child_status=c.child_status;out.service_status=c.service_status;
            if(GAME_LOOP_MUTATION==2&&r->ip==CS_LoadAndStartSelectedLevel&&
               !memory[(((uint32_t)r->ds<<4)+SEG09A9_LevelOutcomeSuccessByte)&0xFFFFFu])
                memory[(((uint32_t)r->ds<<4)+SEG09A9_LevelResourceSelectionByte)&0xFFFFFu]++;
            break;
        }
        default:out.status=LMN_GAME_LOOP_UNSUPPORTED_TRANSFER;return out;
        }
        if(out.core_status) {
            out.status=r->ip==0x04D0?LMN_GAME_LOOP_FATAL_CLEANUP:r->ip==0x4B1C?LMN_GAME_LOOP_RESOURCE_RETRY:
                r->ip==CS_CleanupTerminateInterrupt||r->ip==CS_CleanupAfterTerminate?LMN_GAME_LOOP_DOS_EXIT:
                ((out.core_entry==CS_EnterMainMenu&&out.core_status==LMN_MAIN_MENU_UNBOUND_DOS)||
                 ((out.core_entry==CS_MainMenuStartLevel||out.core_entry==CS_LoadAndStartSelectedLevel)&&
                  (out.core_status==LMN_LEVEL_START_UNBOUND_RESOURCES||out.core_status==LMN_LEVEL_START_UNBOUND_BRIEFING)))?
                LMN_GAME_LOOP_UNBOUND_SERVICE:LMN_GAME_LOOP_CORE_STOP;
            return out;
        }
    }
}
