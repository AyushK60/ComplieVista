	.text
	.file	"c_fixture.c"
	.globl	main                            # -- Begin function main
	.p2align	4, 0x90
	.type	main,@function
main:                                   # @main
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	subq	$48, %rsp
	movl	$0, -4(%rbp)
	movq	.L__const.main.values(%rip), %rax
	movq	%rax, -32(%rbp)
	movq	.L__const.main.values+8(%rip), %rax
	movq	%rax, -24(%rbp)
	movl	$0, -36(%rbp)
	movl	$0, -40(%rbp)
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
	cmpl	$4, -40(%rbp)
	jge	.LBB0_4
# %bb.2:                                #   in Loop: Header=BB0_1 Depth=1
	movl	-36(%rbp), %eax
	movl	%eax, -44(%rbp)                 # 4-byte Spill
	movslq	-40(%rbp), %rax
	movl	-32(%rbp,%rax,4), %edi
	movl	$10, %esi
	callq	scale_and_adjust
	movl	%eax, %ecx
	movl	-44(%rbp), %eax                 # 4-byte Reload
	addl	%ecx, %eax
	movl	%eax, -36(%rbp)
# %bb.3:                                #   in Loop: Header=BB0_1 Depth=1
	movl	-40(%rbp), %eax
	addl	$1, %eax
	movl	%eax, -40(%rbp)
	jmp	.LBB0_1
.LBB0_4:
	movl	-36(%rbp), %esi
	leaq	.L.str(%rip), %rdi
	movb	$0, %al
	callq	printf@PLT
	xorl	%eax, %eax
	addq	$48, %rsp
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.Lfunc_end0:
	.size	main, .Lfunc_end0-main
	.cfi_endproc
                                        # -- End function
	.p2align	4, 0x90                         # -- Begin function scale_and_adjust
	.type	scale_and_adjust,@function
scale_and_adjust:                       # @scale_and_adjust
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	movl	%edi, -8(%rbp)
	movl	%esi, -12(%rbp)
	imull	$3, -8(%rbp), %eax
	movl	%eax, -16(%rbp)
	movl	-16(%rbp), %eax
	cmpl	-12(%rbp), %eax
	jle	.LBB1_2
# %bb.1:
	movl	-12(%rbp), %eax
	movl	%eax, -4(%rbp)
	jmp	.LBB1_3
.LBB1_2:
	movl	-16(%rbp), %eax
	movl	%eax, -4(%rbp)
.LBB1_3:
	movl	-4(%rbp), %eax
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.Lfunc_end1:
	.size	scale_and_adjust, .Lfunc_end1-scale_and_adjust
	.cfi_endproc
                                        # -- End function
	.type	.L__const.main.values,@object   # @__const.main.values
	.section	.rodata.cst16,"aM",@progbits,16
	.p2align	4, 0x0
.L__const.main.values:
	.long	1                               # 0x1
	.long	2                               # 0x2
	.long	3                               # 0x3
	.long	4                               # 0x4
	.size	.L__const.main.values, 16

	.type	.L.str,@object                  # @.str
	.section	.rodata.str1.1,"aMS",@progbits,1
.L.str:
	.asciz	"total=%d\n"
	.size	.L.str, 10

	.ident	"Ubuntu clang version 18.1.3 (1ubuntu1)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym scale_and_adjust
	.addrsig_sym printf
