	.text
	.file	"demo.c"
	.file	0 "/" "/work/demo.c" md5 0xb8e0192d0e86257153cccea19b9623a0
	.globl	sum_squares                     # -- Begin function sum_squares
	.p2align	4, 0x90
	.type	sum_squares,@function
sum_squares:                            # @sum_squares
.Lfunc_begin0:
	.loc	0 7 0                           # /work/demo.c:7:0
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	subq	$16, %rsp
	movl	%edi, -4(%rbp)
.Ltmp0:
	.loc	0 8 9 prologue_end              # /work/demo.c:8:9
	movl	$0, -8(%rbp)
.Ltmp1:
	.loc	0 9 14                          # /work/demo.c:9:14
	movl	$0, -12(%rbp)
.LBB0_1:                                # =>This Inner Loop Header: Depth=1
.Ltmp2:
	.loc	0 9 21 is_stmt 0                # /work/demo.c:9:21
	movl	-12(%rbp), %eax
	.loc	0 9 23                          # /work/demo.c:9:23
	cmpl	-4(%rbp), %eax
.Ltmp3:
	.loc	0 9 5                           # /work/demo.c:9:5
	jge	.LBB0_4
# %bb.2:                                #   in Loop: Header=BB0_1 Depth=1
.Ltmp4:
	.loc	0 10 25 is_stmt 1               # /work/demo.c:10:25
	movl	-12(%rbp), %edi
	.loc	0 10 18 is_stmt 0               # /work/demo.c:10:18
	callq	square
	.loc	0 10 15                         # /work/demo.c:10:15
	addl	-8(%rbp), %eax
	movl	%eax, -8(%rbp)
.Ltmp5:
# %bb.3:                                #   in Loop: Header=BB0_1 Depth=1
	.loc	0 9 29 is_stmt 1                # /work/demo.c:9:29
	movl	-12(%rbp), %eax
	addl	$1, %eax
	movl	%eax, -12(%rbp)
	.loc	0 9 5 is_stmt 0                 # /work/demo.c:9:5
	jmp	.LBB0_1
.Ltmp6:
.LBB0_4:
	.loc	0 12 12 is_stmt 1               # /work/demo.c:12:12
	movl	-8(%rbp), %eax
	.loc	0 12 5 epilogue_begin is_stmt 0 # /work/demo.c:12:5
	addq	$16, %rsp
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.Ltmp7:
.Lfunc_end0:
	.size	sum_squares, .Lfunc_end0-sum_squares
	.cfi_endproc
                                        # -- End function
	.p2align	4, 0x90                         # -- Begin function square
	.type	square,@function
square:                                 # @square
.Lfunc_begin1:
	.loc	0 3 0 is_stmt 1                 # /work/demo.c:3:0
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	movl	%edi, -4(%rbp)
.Ltmp8:
	.loc	0 4 12 prologue_end             # /work/demo.c:4:12
	movl	-4(%rbp), %eax
	.loc	0 4 14 is_stmt 0                # /work/demo.c:4:14
	imull	-4(%rbp), %eax
	.loc	0 4 5 epilogue_begin            # /work/demo.c:4:5
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.Ltmp9:
.Lfunc_end1:
	.size	square, .Lfunc_end1-square
	.cfi_endproc
                                        # -- End function
	.globl	main                            # -- Begin function main
	.p2align	4, 0x90
	.type	main,@function
main:                                   # @main
.Lfunc_begin2:
	.loc	0 15 0 is_stmt 1                # /work/demo.c:15:0
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	subq	$16, %rsp
	movl	$0, -4(%rbp)
.Ltmp10:
	.loc	0 16 9 prologue_end             # /work/demo.c:16:9
	movl	$42, -8(%rbp)
	.loc	0 17 20                         # /work/demo.c:17:20
	movl	$10, %edi
	callq	sum_squares
	movl	%eax, %esi
	.loc	0 17 5 is_stmt 0                # /work/demo.c:17:5
	leaq	.L.str(%rip), %rdi
	movb	$0, %al
	callq	printf@PLT
	.loc	0 18 5 is_stmt 1                # /work/demo.c:18:5
	xorl	%eax, %eax
	.loc	0 18 5 epilogue_begin is_stmt 0 # /work/demo.c:18:5
	addq	$16, %rsp
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.Ltmp11:
.Lfunc_end2:
	.size	main, .Lfunc_end2-main
	.cfi_endproc
                                        # -- End function
	.type	.L.str,@object                  # @.str
	.section	.rodata.str1.1,"aMS",@progbits,1
.L.str:
	.asciz	"%d\n"
	.size	.L.str, 4

	.section	.debug_abbrev,"",@progbits
	.byte	1                               # Abbreviation Code
	.byte	17                              # DW_TAG_compile_unit
	.byte	1                               # DW_CHILDREN_yes
	.byte	37                              # DW_AT_producer
	.byte	37                              # DW_FORM_strx1
	.byte	19                              # DW_AT_language
	.byte	5                               # DW_FORM_data2
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	114                             # DW_AT_str_offsets_base
	.byte	23                              # DW_FORM_sec_offset
	.byte	16                              # DW_AT_stmt_list
	.byte	23                              # DW_FORM_sec_offset
	.byte	27                              # DW_AT_comp_dir
	.byte	37                              # DW_FORM_strx1
	.byte	17                              # DW_AT_low_pc
	.byte	27                              # DW_FORM_addrx
	.byte	18                              # DW_AT_high_pc
	.byte	6                               # DW_FORM_data4
	.byte	115                             # DW_AT_addr_base
	.byte	23                              # DW_FORM_sec_offset
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	2                               # Abbreviation Code
	.byte	52                              # DW_TAG_variable
	.byte	0                               # DW_CHILDREN_no
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	58                              # DW_AT_decl_file
	.byte	11                              # DW_FORM_data1
	.byte	59                              # DW_AT_decl_line
	.byte	11                              # DW_FORM_data1
	.byte	2                               # DW_AT_location
	.byte	24                              # DW_FORM_exprloc
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	3                               # Abbreviation Code
	.byte	1                               # DW_TAG_array_type
	.byte	1                               # DW_CHILDREN_yes
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	4                               # Abbreviation Code
	.byte	33                              # DW_TAG_subrange_type
	.byte	0                               # DW_CHILDREN_no
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	55                              # DW_AT_count
	.byte	11                              # DW_FORM_data1
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	5                               # Abbreviation Code
	.byte	36                              # DW_TAG_base_type
	.byte	0                               # DW_CHILDREN_no
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	62                              # DW_AT_encoding
	.byte	11                              # DW_FORM_data1
	.byte	11                              # DW_AT_byte_size
	.byte	11                              # DW_FORM_data1
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	6                               # Abbreviation Code
	.byte	36                              # DW_TAG_base_type
	.byte	0                               # DW_CHILDREN_no
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	11                              # DW_AT_byte_size
	.byte	11                              # DW_FORM_data1
	.byte	62                              # DW_AT_encoding
	.byte	11                              # DW_FORM_data1
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	7                               # Abbreviation Code
	.byte	46                              # DW_TAG_subprogram
	.byte	1                               # DW_CHILDREN_yes
	.byte	17                              # DW_AT_low_pc
	.byte	27                              # DW_FORM_addrx
	.byte	18                              # DW_AT_high_pc
	.byte	6                               # DW_FORM_data4
	.byte	64                              # DW_AT_frame_base
	.byte	24                              # DW_FORM_exprloc
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	58                              # DW_AT_decl_file
	.byte	11                              # DW_FORM_data1
	.byte	59                              # DW_AT_decl_line
	.byte	11                              # DW_FORM_data1
	.byte	39                              # DW_AT_prototyped
	.byte	25                              # DW_FORM_flag_present
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	63                              # DW_AT_external
	.byte	25                              # DW_FORM_flag_present
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	8                               # Abbreviation Code
	.byte	5                               # DW_TAG_formal_parameter
	.byte	0                               # DW_CHILDREN_no
	.byte	2                               # DW_AT_location
	.byte	24                              # DW_FORM_exprloc
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	58                              # DW_AT_decl_file
	.byte	11                              # DW_FORM_data1
	.byte	59                              # DW_AT_decl_line
	.byte	11                              # DW_FORM_data1
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	9                               # Abbreviation Code
	.byte	52                              # DW_TAG_variable
	.byte	0                               # DW_CHILDREN_no
	.byte	2                               # DW_AT_location
	.byte	24                              # DW_FORM_exprloc
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	58                              # DW_AT_decl_file
	.byte	11                              # DW_FORM_data1
	.byte	59                              # DW_AT_decl_line
	.byte	11                              # DW_FORM_data1
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	10                              # Abbreviation Code
	.byte	11                              # DW_TAG_lexical_block
	.byte	1                               # DW_CHILDREN_yes
	.byte	17                              # DW_AT_low_pc
	.byte	27                              # DW_FORM_addrx
	.byte	18                              # DW_AT_high_pc
	.byte	6                               # DW_FORM_data4
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	11                              # Abbreviation Code
	.byte	46                              # DW_TAG_subprogram
	.byte	1                               # DW_CHILDREN_yes
	.byte	17                              # DW_AT_low_pc
	.byte	27                              # DW_FORM_addrx
	.byte	18                              # DW_AT_high_pc
	.byte	6                               # DW_FORM_data4
	.byte	64                              # DW_AT_frame_base
	.byte	24                              # DW_FORM_exprloc
	.byte	3                               # DW_AT_name
	.byte	37                              # DW_FORM_strx1
	.byte	58                              # DW_AT_decl_file
	.byte	11                              # DW_FORM_data1
	.byte	59                              # DW_AT_decl_line
	.byte	11                              # DW_FORM_data1
	.byte	39                              # DW_AT_prototyped
	.byte	25                              # DW_FORM_flag_present
	.byte	73                              # DW_AT_type
	.byte	19                              # DW_FORM_ref4
	.byte	0                               # EOM(1)
	.byte	0                               # EOM(2)
	.byte	0                               # EOM(3)
	.section	.debug_info,"",@progbits
.Lcu_begin0:
	.long	.Ldebug_info_end0-.Ldebug_info_start0 # Length of Unit
.Ldebug_info_start0:
	.short	5                               # DWARF version number
	.byte	1                               # DWARF Unit Type
	.byte	8                               # Address Size (in bytes)
	.long	.debug_abbrev                   # Offset Into Abbrev. Section
	.byte	1                               # Abbrev [1] 0xc:0xa8 DW_TAG_compile_unit
	.byte	0                               # DW_AT_producer
	.short	29                              # DW_AT_language
	.byte	1                               # DW_AT_name
	.long	.Lstr_offsets_base0             # DW_AT_str_offsets_base
	.long	.Lline_table_start0             # DW_AT_stmt_list
	.byte	2                               # DW_AT_comp_dir
	.byte	1                               # DW_AT_low_pc
	.long	.Lfunc_end2-.Lfunc_begin0       # DW_AT_high_pc
	.long	.Laddr_table_base0              # DW_AT_addr_base
	.byte	2                               # Abbrev [2] 0x23:0xa DW_TAG_variable
	.long	45                              # DW_AT_type
	.byte	0                               # DW_AT_decl_file
	.byte	17                              # DW_AT_decl_line
	.byte	2                               # DW_AT_location
	.byte	161
	.byte	0
	.byte	3                               # Abbrev [3] 0x2d:0xc DW_TAG_array_type
	.long	57                              # DW_AT_type
	.byte	4                               # Abbrev [4] 0x32:0x6 DW_TAG_subrange_type
	.long	61                              # DW_AT_type
	.byte	4                               # DW_AT_count
	.byte	0                               # End Of Children Mark
	.byte	5                               # Abbrev [5] 0x39:0x4 DW_TAG_base_type
	.byte	3                               # DW_AT_name
	.byte	6                               # DW_AT_encoding
	.byte	1                               # DW_AT_byte_size
	.byte	6                               # Abbrev [6] 0x3d:0x4 DW_TAG_base_type
	.byte	4                               # DW_AT_name
	.byte	8                               # DW_AT_byte_size
	.byte	7                               # DW_AT_encoding
	.byte	7                               # Abbrev [7] 0x41:0x38 DW_TAG_subprogram
	.byte	1                               # DW_AT_low_pc
	.long	.Lfunc_end0-.Lfunc_begin0       # DW_AT_high_pc
	.byte	1                               # DW_AT_frame_base
	.byte	86
	.byte	5                               # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	7                               # DW_AT_decl_line
                                        # DW_AT_prototyped
	.long	175                             # DW_AT_type
                                        # DW_AT_external
	.byte	8                               # Abbrev [8] 0x50:0xb DW_TAG_formal_parameter
	.byte	2                               # DW_AT_location
	.byte	145
	.byte	124
	.byte	9                               # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	7                               # DW_AT_decl_line
	.long	175                             # DW_AT_type
	.byte	9                               # Abbrev [9] 0x5b:0xb DW_TAG_variable
	.byte	2                               # DW_AT_location
	.byte	145
	.byte	120
	.byte	10                              # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	8                               # DW_AT_decl_line
	.long	175                             # DW_AT_type
	.byte	10                              # Abbrev [10] 0x66:0x12 DW_TAG_lexical_block
	.byte	2                               # DW_AT_low_pc
	.long	.Ltmp6-.Ltmp1                   # DW_AT_high_pc
	.byte	9                               # Abbrev [9] 0x6c:0xb DW_TAG_variable
	.byte	2                               # DW_AT_location
	.byte	145
	.byte	116
	.byte	11                              # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	9                               # DW_AT_decl_line
	.long	175                             # DW_AT_type
	.byte	0                               # End Of Children Mark
	.byte	0                               # End Of Children Mark
	.byte	11                              # Abbrev [11] 0x79:0x1b DW_TAG_subprogram
	.byte	3                               # DW_AT_low_pc
	.long	.Lfunc_end1-.Lfunc_begin1       # DW_AT_high_pc
	.byte	1                               # DW_AT_frame_base
	.byte	86
	.byte	7                               # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	3                               # DW_AT_decl_line
                                        # DW_AT_prototyped
	.long	175                             # DW_AT_type
	.byte	8                               # Abbrev [8] 0x88:0xb DW_TAG_formal_parameter
	.byte	2                               # DW_AT_location
	.byte	145
	.byte	124
	.byte	12                              # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	3                               # DW_AT_decl_line
	.long	175                             # DW_AT_type
	.byte	0                               # End Of Children Mark
	.byte	7                               # Abbrev [7] 0x94:0x1b DW_TAG_subprogram
	.byte	4                               # DW_AT_low_pc
	.long	.Lfunc_end2-.Lfunc_begin2       # DW_AT_high_pc
	.byte	1                               # DW_AT_frame_base
	.byte	86
	.byte	8                               # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	15                              # DW_AT_decl_line
                                        # DW_AT_prototyped
	.long	175                             # DW_AT_type
                                        # DW_AT_external
	.byte	9                               # Abbrev [9] 0xa3:0xb DW_TAG_variable
	.byte	2                               # DW_AT_location
	.byte	145
	.byte	120
	.byte	13                              # DW_AT_name
	.byte	0                               # DW_AT_decl_file
	.byte	16                              # DW_AT_decl_line
	.long	175                             # DW_AT_type
	.byte	0                               # End Of Children Mark
	.byte	5                               # Abbrev [5] 0xaf:0x4 DW_TAG_base_type
	.byte	6                               # DW_AT_name
	.byte	5                               # DW_AT_encoding
	.byte	4                               # DW_AT_byte_size
	.byte	0                               # End Of Children Mark
.Ldebug_info_end0:
	.section	.debug_str_offsets,"",@progbits
	.long	60                              # Length of String Offsets Set
	.short	5
	.short	0
.Lstr_offsets_base0:
	.section	.debug_str,"MS",@progbits,1
.Linfo_string0:
	.asciz	"Ubuntu clang version 18.1.3 (1ubuntu1)" # string offset=0
.Linfo_string1:
	.asciz	"/work/demo.c"                  # string offset=39
.Linfo_string2:
	.asciz	"/"                             # string offset=52
.Linfo_string3:
	.asciz	"char"                          # string offset=54
.Linfo_string4:
	.asciz	"__ARRAY_SIZE_TYPE__"           # string offset=59
.Linfo_string5:
	.asciz	"sum_squares"                   # string offset=79
.Linfo_string6:
	.asciz	"int"                           # string offset=91
.Linfo_string7:
	.asciz	"square"                        # string offset=95
.Linfo_string8:
	.asciz	"main"                          # string offset=102
.Linfo_string9:
	.asciz	"n"                             # string offset=107
.Linfo_string10:
	.asciz	"total"                         # string offset=109
.Linfo_string11:
	.asciz	"i"                             # string offset=115
.Linfo_string12:
	.asciz	"x"                             # string offset=117
.Linfo_string13:
	.asciz	"unused"                        # string offset=119
	.section	.debug_str_offsets,"",@progbits
	.long	.Linfo_string0
	.long	.Linfo_string1
	.long	.Linfo_string2
	.long	.Linfo_string3
	.long	.Linfo_string4
	.long	.Linfo_string5
	.long	.Linfo_string6
	.long	.Linfo_string7
	.long	.Linfo_string8
	.long	.Linfo_string9
	.long	.Linfo_string10
	.long	.Linfo_string11
	.long	.Linfo_string12
	.long	.Linfo_string13
	.section	.debug_addr,"",@progbits
	.long	.Ldebug_addr_end0-.Ldebug_addr_start0 # Length of contribution
.Ldebug_addr_start0:
	.short	5                               # DWARF version number
	.byte	8                               # Address size
	.byte	0                               # Segment selector size
.Laddr_table_base0:
	.quad	.L.str
	.quad	.Lfunc_begin0
	.quad	.Ltmp1
	.quad	.Lfunc_begin1
	.quad	.Lfunc_begin2
.Ldebug_addr_end0:
	.ident	"Ubuntu clang version 18.1.3 (1ubuntu1)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	.addrsig_sym sum_squares
	.addrsig_sym square
	.addrsig_sym printf
	.section	.debug_line,"",@progbits
.Lline_table_start0:
