; ModuleID = '/work/demo.c'
source_filename = "/work/demo.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@.str = private unnamed_addr constant [4 x i8] c"%d\0A\00", align 1, !dbg !0

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @sum_squares(i32 noundef %0) #0 !dbg !18 {
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 %0, ptr %2, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !23, metadata !DIExpression()), !dbg !24
  call void @llvm.dbg.declare(metadata ptr %3, metadata !25, metadata !DIExpression()), !dbg !26
  store i32 0, ptr %3, align 4, !dbg !26
  call void @llvm.dbg.declare(metadata ptr %4, metadata !27, metadata !DIExpression()), !dbg !29
  store i32 0, ptr %4, align 4, !dbg !29
  br label %5, !dbg !30

5:                                                ; preds = %14, %1
  %6 = load i32, ptr %4, align 4, !dbg !31
  %7 = load i32, ptr %2, align 4, !dbg !33
  %8 = icmp slt i32 %6, %7, !dbg !34
  br i1 %8, label %9, label %17, !dbg !35

9:                                                ; preds = %5
  %10 = load i32, ptr %4, align 4, !dbg !36
  %11 = call i32 @square(i32 noundef %10), !dbg !38
  %12 = load i32, ptr %3, align 4, !dbg !39
  %13 = add nsw i32 %12, %11, !dbg !39
  store i32 %13, ptr %3, align 4, !dbg !39
  br label %14, !dbg !40

14:                                               ; preds = %9
  %15 = load i32, ptr %4, align 4, !dbg !41
  %16 = add nsw i32 %15, 1, !dbg !41
  store i32 %16, ptr %4, align 4, !dbg !41
  br label %5, !dbg !42, !llvm.loop !43

17:                                               ; preds = %5
  %18 = load i32, ptr %3, align 4, !dbg !46
  ret i32 %18, !dbg !47
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define internal i32 @square(i32 noundef %0) #0 !dbg !48 {
  %2 = alloca i32, align 4
  store i32 %0, ptr %2, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !49, metadata !DIExpression()), !dbg !50
  %3 = load i32, ptr %2, align 4, !dbg !51
  %4 = load i32, ptr %2, align 4, !dbg !52
  %5 = mul nsw i32 %3, %4, !dbg !53
  ret i32 %5, !dbg !54
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !55 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !58, metadata !DIExpression()), !dbg !59
  store i32 42, ptr %2, align 4, !dbg !59
  %3 = call i32 @sum_squares(i32 noundef 10), !dbg !60
  %4 = call i32 (ptr, ...) @printf(ptr noundef @.str, i32 noundef %3), !dbg !61
  ret i32 0, !dbg !62
}

declare i32 @printf(ptr noundef, ...) #2

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!7}
!llvm.module.flags = !{!10, !11, !12, !13, !14, !15, !16}
!llvm.ident = !{!17}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(scope: null, file: !2, line: 17, type: !3, isLocal: true, isDefinition: true)
!2 = !DIFile(filename: "/work/demo.c", directory: "", checksumkind: CSK_MD5, checksum: "b8e0192d0e86257153cccea19b9623a0")
!3 = !DICompositeType(tag: DW_TAG_array_type, baseType: !4, size: 32, elements: !5)
!4 = !DIBasicType(name: "char", size: 8, encoding: DW_ATE_signed_char)
!5 = !{!6}
!6 = !DISubrange(count: 4)
!7 = distinct !DICompileUnit(language: DW_LANG_C11, file: !8, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !9, splitDebugInlining: false, nameTableKind: None)
!8 = !DIFile(filename: "/work/demo.c", directory: "/", checksumkind: CSK_MD5, checksum: "b8e0192d0e86257153cccea19b9623a0")
!9 = !{!0}
!10 = !{i32 7, !"Dwarf Version", i32 5}
!11 = !{i32 2, !"Debug Info Version", i32 3}
!12 = !{i32 1, !"wchar_size", i32 4}
!13 = !{i32 8, !"PIC Level", i32 2}
!14 = !{i32 7, !"PIE Level", i32 2}
!15 = !{i32 7, !"uwtable", i32 2}
!16 = !{i32 7, !"frame-pointer", i32 2}
!17 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!18 = distinct !DISubprogram(name: "sum_squares", scope: !2, file: !2, line: 7, type: !19, scopeLine: 7, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !7, retainedNodes: !22)
!19 = !DISubroutineType(types: !20)
!20 = !{!21, !21}
!21 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!22 = !{}
!23 = !DILocalVariable(name: "n", arg: 1, scope: !18, file: !2, line: 7, type: !21)
!24 = !DILocation(line: 7, column: 21, scope: !18)
!25 = !DILocalVariable(name: "total", scope: !18, file: !2, line: 8, type: !21)
!26 = !DILocation(line: 8, column: 9, scope: !18)
!27 = !DILocalVariable(name: "i", scope: !28, file: !2, line: 9, type: !21)
!28 = distinct !DILexicalBlock(scope: !18, file: !2, line: 9, column: 5)
!29 = !DILocation(line: 9, column: 14, scope: !28)
!30 = !DILocation(line: 9, column: 10, scope: !28)
!31 = !DILocation(line: 9, column: 21, scope: !32)
!32 = distinct !DILexicalBlock(scope: !28, file: !2, line: 9, column: 5)
!33 = !DILocation(line: 9, column: 25, scope: !32)
!34 = !DILocation(line: 9, column: 23, scope: !32)
!35 = !DILocation(line: 9, column: 5, scope: !28)
!36 = !DILocation(line: 10, column: 25, scope: !37)
!37 = distinct !DILexicalBlock(scope: !32, file: !2, line: 9, column: 33)
!38 = !DILocation(line: 10, column: 18, scope: !37)
!39 = !DILocation(line: 10, column: 15, scope: !37)
!40 = !DILocation(line: 11, column: 5, scope: !37)
!41 = !DILocation(line: 9, column: 29, scope: !32)
!42 = !DILocation(line: 9, column: 5, scope: !32)
!43 = distinct !{!43, !35, !44, !45}
!44 = !DILocation(line: 11, column: 5, scope: !28)
!45 = !{!"llvm.loop.mustprogress"}
!46 = !DILocation(line: 12, column: 12, scope: !18)
!47 = !DILocation(line: 12, column: 5, scope: !18)
!48 = distinct !DISubprogram(name: "square", scope: !2, file: !2, line: 3, type: !19, scopeLine: 3, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !7, retainedNodes: !22)
!49 = !DILocalVariable(name: "x", arg: 1, scope: !48, file: !2, line: 3, type: !21)
!50 = !DILocation(line: 3, column: 23, scope: !48)
!51 = !DILocation(line: 4, column: 12, scope: !48)
!52 = !DILocation(line: 4, column: 16, scope: !48)
!53 = !DILocation(line: 4, column: 14, scope: !48)
!54 = !DILocation(line: 4, column: 5, scope: !48)
!55 = distinct !DISubprogram(name: "main", scope: !2, file: !2, line: 15, type: !56, scopeLine: 15, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !7, retainedNodes: !22)
!56 = !DISubroutineType(types: !57)
!57 = !{!21}
!58 = !DILocalVariable(name: "unused", scope: !55, file: !2, line: 16, type: !21)
!59 = !DILocation(line: 16, column: 9, scope: !55)
!60 = !DILocation(line: 17, column: 20, scope: !55)
!61 = !DILocation(line: 17, column: 5, scope: !55)
!62 = !DILocation(line: 18, column: 5, scope: !55)
