; ModuleID = '/work/demo.c'
source_filename = "/work/demo.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@.str = private unnamed_addr constant [4 x i8] c"%d\0A\00", align 1, !dbg !0

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(none) uwtable
define dso_local i32 @sum_squares(i32 noundef %0) local_unnamed_addr #0 !dbg !19 {
  tail call void @llvm.dbg.value(metadata i32 %0, metadata !24, metadata !DIExpression()), !dbg !28
  tail call void @llvm.dbg.value(metadata i32 0, metadata !25, metadata !DIExpression()), !dbg !28
  tail call void @llvm.dbg.value(metadata i32 0, metadata !26, metadata !DIExpression()), !dbg !29
  %2 = icmp sgt i32 %0, 0, !dbg !30
  br i1 %2, label %3, label %21, !dbg !32

3:                                                ; preds = %1
  %4 = add nsw i32 %0, -1, !dbg !32
  %5 = zext nneg i32 %4 to i33, !dbg !32
  %6 = add nsw i32 %0, -2, !dbg !32
  %7 = zext i32 %6 to i33, !dbg !32
  %8 = mul i33 %5, %7, !dbg !32
  %9 = add nsw i32 %0, -3, !dbg !32
  %10 = zext i32 %9 to i33, !dbg !32
  %11 = mul i33 %8, %10, !dbg !32
  %12 = lshr i33 %11, 1, !dbg !32
  %13 = trunc i33 %12 to i32, !dbg !32
  %14 = mul i32 %13, 1431655766, !dbg !32
  %15 = add i32 %14, %0, !dbg !32
  %16 = lshr i33 %8, 1, !dbg !32
  %17 = trunc i33 %16 to i32, !dbg !32
  %18 = mul i32 %17, 3, !dbg !32
  %19 = add i32 %15, %18, !dbg !32
  tail call void @llvm.dbg.value(metadata i32 undef, metadata !26, metadata !DIExpression()), !dbg !29
  tail call void @llvm.dbg.value(metadata i32 poison, metadata !25, metadata !DIExpression()), !dbg !28
  %20 = add i32 %19, -1, !dbg !32
  br label %21, !dbg !33

21:                                               ; preds = %3, %1
  %22 = phi i32 [ 0, %1 ], [ %20, %3 ], !dbg !28
  ret i32 %22, !dbg !33
}

; Function Attrs: nofree nounwind uwtable
define dso_local noundef i32 @main() local_unnamed_addr #1 !dbg !34 {
  tail call void @llvm.dbg.value(metadata i32 42, metadata !38, metadata !DIExpression()), !dbg !39
  %1 = tail call i32 (ptr, ...) @printf(ptr noundef nonnull dereferenceable(1) @.str, i32 noundef 285), !dbg !40
  ret i32 0, !dbg !41
}

; Function Attrs: nofree nounwind
declare !dbg !42 noundef i32 @printf(ptr nocapture noundef readonly, ...) local_unnamed_addr #2

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.value(metadata, metadata, metadata) #3

attributes #0 = { mustprogress nofree norecurse nosync nounwind willreturn memory(none) uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nounwind uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #2 = { nofree nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.dbg.cu = !{!7}
!llvm.module.flags = !{!10, !11, !12, !13, !14, !15, !16, !17}
!llvm.ident = !{!18}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(scope: null, file: !2, line: 17, type: !3, isLocal: true, isDefinition: true)
!2 = !DIFile(filename: "/work/demo.c", directory: "", checksumkind: CSK_MD5, checksum: "b8e0192d0e86257153cccea19b9623a0")
!3 = !DICompositeType(tag: DW_TAG_array_type, baseType: !4, size: 32, elements: !5)
!4 = !DIBasicType(name: "char", size: 8, encoding: DW_ATE_signed_char)
!5 = !{!6}
!6 = !DISubrange(count: 4)
!7 = distinct !DICompileUnit(language: DW_LANG_C11, file: !8, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: true, runtimeVersion: 0, emissionKind: FullDebug, globals: !9, splitDebugInlining: false, nameTableKind: None)
!8 = !DIFile(filename: "/work/demo.c", directory: "/", checksumkind: CSK_MD5, checksum: "b8e0192d0e86257153cccea19b9623a0")
!9 = !{!0}
!10 = !{i32 7, !"Dwarf Version", i32 5}
!11 = !{i32 2, !"Debug Info Version", i32 3}
!12 = !{i32 1, !"wchar_size", i32 4}
!13 = !{i32 8, !"PIC Level", i32 2}
!14 = !{i32 7, !"PIE Level", i32 2}
!15 = !{i32 7, !"uwtable", i32 2}
!16 = !{i32 7, !"frame-pointer", i32 2}
!17 = !{i32 7, !"debug-info-assignment-tracking", i1 true}
!18 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!19 = distinct !DISubprogram(name: "sum_squares", scope: !2, file: !2, line: 7, type: !20, scopeLine: 7, flags: DIFlagPrototyped | DIFlagAllCallsDescribed, spFlags: DISPFlagDefinition | DISPFlagOptimized, unit: !7, retainedNodes: !23)
!20 = !DISubroutineType(types: !21)
!21 = !{!22, !22}
!22 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!23 = !{!24, !25, !26}
!24 = !DILocalVariable(name: "n", arg: 1, scope: !19, file: !2, line: 7, type: !22)
!25 = !DILocalVariable(name: "total", scope: !19, file: !2, line: 8, type: !22)
!26 = !DILocalVariable(name: "i", scope: !27, file: !2, line: 9, type: !22)
!27 = distinct !DILexicalBlock(scope: !19, file: !2, line: 9, column: 5)
!28 = !DILocation(line: 0, scope: !19)
!29 = !DILocation(line: 0, scope: !27)
!30 = !DILocation(line: 9, column: 23, scope: !31)
!31 = distinct !DILexicalBlock(scope: !27, file: !2, line: 9, column: 5)
!32 = !DILocation(line: 9, column: 5, scope: !27)
!33 = !DILocation(line: 12, column: 5, scope: !19)
!34 = distinct !DISubprogram(name: "main", scope: !2, file: !2, line: 15, type: !35, scopeLine: 15, flags: DIFlagPrototyped | DIFlagAllCallsDescribed, spFlags: DISPFlagDefinition | DISPFlagOptimized, unit: !7, retainedNodes: !37)
!35 = !DISubroutineType(types: !36)
!36 = !{!22}
!37 = !{!38}
!38 = !DILocalVariable(name: "unused", scope: !34, file: !2, line: 16, type: !22)
!39 = !DILocation(line: 0, scope: !34)
!40 = !DILocation(line: 17, column: 5, scope: !34)
!41 = !DILocation(line: 18, column: 5, scope: !34)
!42 = !DISubprogram(name: "printf", scope: !43, file: !43, line: 363, type: !44, flags: DIFlagPrototyped, spFlags: DISPFlagOptimized)
!43 = !DIFile(filename: "/usr/include/stdio.h", directory: "", checksumkind: CSK_MD5, checksum: "1e435c46987a169d9f9186f63a512303")
!44 = !DISubroutineType(types: !45)
!45 = !{!22, !46, null}
!46 = !DIDerivedType(tag: DW_TAG_restrict_type, baseType: !47)
!47 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !48, size: 64)
!48 = !DIDerivedType(tag: DW_TAG_const_type, baseType: !4)
