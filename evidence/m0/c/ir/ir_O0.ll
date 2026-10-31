; ModuleID = '/mnt/e/ComplieVista/demos/m0/c_fixture.c'
source_filename = "/mnt/e/ComplieVista/demos/m0/c_fixture.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@__const.main.values = private unnamed_addr constant [4 x i32] [i32 1, i32 2, i32 3, i32 4], align 16
@.str = private unnamed_addr constant [10 x i8] c"total=%d\0A\00", align 1, !dbg !0

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !18 {
  %1 = alloca i32, align 4
  %2 = alloca [4 x i32], align 16
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !23, metadata !DIExpression()), !dbg !27
  call void @llvm.memcpy.p0.p0.i64(ptr align 16 %2, ptr align 16 @__const.main.values, i64 16, i1 false), !dbg !27
  call void @llvm.dbg.declare(metadata ptr %3, metadata !28, metadata !DIExpression()), !dbg !29
  store i32 0, ptr %3, align 4, !dbg !29
  call void @llvm.dbg.declare(metadata ptr %4, metadata !30, metadata !DIExpression()), !dbg !32
  store i32 0, ptr %4, align 4, !dbg !32
  br label %5, !dbg !33

5:                                                ; preds = %16, %0
  %6 = load i32, ptr %4, align 4, !dbg !34
  %7 = icmp slt i32 %6, 4, !dbg !36
  br i1 %7, label %8, label %19, !dbg !37

8:                                                ; preds = %5
  %9 = load i32, ptr %3, align 4, !dbg !38
  %10 = load i32, ptr %4, align 4, !dbg !40
  %11 = sext i32 %10 to i64, !dbg !41
  %12 = getelementptr inbounds [4 x i32], ptr %2, i64 0, i64 %11, !dbg !41
  %13 = load i32, ptr %12, align 4, !dbg !41
  %14 = call i32 @scale_and_adjust(i32 noundef %13, i32 noundef 10), !dbg !42
  %15 = add nsw i32 %9, %14, !dbg !43
  store i32 %15, ptr %3, align 4, !dbg !44
  br label %16, !dbg !45

16:                                               ; preds = %8
  %17 = load i32, ptr %4, align 4, !dbg !46
  %18 = add nsw i32 %17, 1, !dbg !47
  store i32 %18, ptr %4, align 4, !dbg !48
  br label %5, !dbg !49, !llvm.loop !50

19:                                               ; preds = %5
  %20 = load i32, ptr %3, align 4, !dbg !53
  %21 = call i32 (ptr, ...) @printf(ptr noundef @.str, i32 noundef %20), !dbg !54
  ret i32 0, !dbg !55
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: nocallback nofree nounwind willreturn memory(argmem: readwrite)
declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg) #2

; Function Attrs: noinline nounwind optnone uwtable
define internal i32 @scale_and_adjust(i32 noundef %0, i32 noundef %1) #0 !dbg !56 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  store i32 %0, ptr %4, align 4
  call void @llvm.dbg.declare(metadata ptr %4, metadata !59, metadata !DIExpression()), !dbg !60
  store i32 %1, ptr %5, align 4
  call void @llvm.dbg.declare(metadata ptr %5, metadata !61, metadata !DIExpression()), !dbg !62
  call void @llvm.dbg.declare(metadata ptr %6, metadata !63, metadata !DIExpression()), !dbg !64
  %7 = load i32, ptr %4, align 4, !dbg !65
  %8 = mul nsw i32 %7, 3, !dbg !66
  store i32 %8, ptr %6, align 4, !dbg !64
  %9 = load i32, ptr %6, align 4, !dbg !67
  %10 = load i32, ptr %5, align 4, !dbg !69
  %11 = icmp sgt i32 %9, %10, !dbg !70
  br i1 %11, label %12, label %14, !dbg !71

12:                                               ; preds = %2
  %13 = load i32, ptr %5, align 4, !dbg !72
  store i32 %13, ptr %3, align 4, !dbg !74
  br label %16, !dbg !74

14:                                               ; preds = %2
  %15 = load i32, ptr %6, align 4, !dbg !75
  store i32 %15, ptr %3, align 4, !dbg !76
  br label %16, !dbg !76

16:                                               ; preds = %14, %12
  %17 = load i32, ptr %3, align 4, !dbg !77
  ret i32 %17, !dbg !77
}

declare i32 @printf(ptr noundef, ...) #3

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { nocallback nofree nounwind willreturn memory(argmem: readwrite) }
attributes #3 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!7}
!llvm.module.flags = !{!10, !11, !12, !13, !14, !15, !16}
!llvm.ident = !{!17}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(scope: null, file: !2, line: 21, type: !3, isLocal: true, isDefinition: true)
!2 = !DIFile(filename: "demos/m0/c_fixture.c", directory: "/mnt/e/ComplieVista", checksumkind: CSK_MD5, checksum: "ee342a0a824b984bfa4bc1a80d596c54")
!3 = !DICompositeType(tag: DW_TAG_array_type, baseType: !4, size: 80, elements: !5)
!4 = !DIBasicType(name: "char", size: 8, encoding: DW_ATE_signed_char)
!5 = !{!6}
!6 = !DISubrange(count: 10)
!7 = distinct !DICompileUnit(language: DW_LANG_C11, file: !8, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !9, splitDebugInlining: false, nameTableKind: None)
!8 = !DIFile(filename: "/mnt/e/ComplieVista/demos/m0/c_fixture.c", directory: "/mnt/e/ComplieVista", checksumkind: CSK_MD5, checksum: "ee342a0a824b984bfa4bc1a80d596c54")
!9 = !{!0}
!10 = !{i32 7, !"Dwarf Version", i32 5}
!11 = !{i32 2, !"Debug Info Version", i32 3}
!12 = !{i32 1, !"wchar_size", i32 4}
!13 = !{i32 8, !"PIC Level", i32 2}
!14 = !{i32 7, !"PIE Level", i32 2}
!15 = !{i32 7, !"uwtable", i32 2}
!16 = !{i32 7, !"frame-pointer", i32 2}
!17 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!18 = distinct !DISubprogram(name: "main", scope: !2, file: !2, line: 15, type: !19, scopeLine: 15, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !7, retainedNodes: !22)
!19 = !DISubroutineType(types: !20)
!20 = !{!21}
!21 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!22 = !{}
!23 = !DILocalVariable(name: "values", scope: !18, file: !2, line: 16, type: !24)
!24 = !DICompositeType(tag: DW_TAG_array_type, baseType: !21, size: 128, elements: !25)
!25 = !{!26}
!26 = !DISubrange(count: 4)
!27 = !DILocation(line: 16, column: 9, scope: !18)
!28 = !DILocalVariable(name: "total", scope: !18, file: !2, line: 17, type: !21)
!29 = !DILocation(line: 17, column: 9, scope: !18)
!30 = !DILocalVariable(name: "i", scope: !31, file: !2, line: 18, type: !21)
!31 = distinct !DILexicalBlock(scope: !18, file: !2, line: 18, column: 5)
!32 = !DILocation(line: 18, column: 14, scope: !31)
!33 = !DILocation(line: 18, column: 10, scope: !31)
!34 = !DILocation(line: 18, column: 21, scope: !35)
!35 = distinct !DILexicalBlock(scope: !31, file: !2, line: 18, column: 5)
!36 = !DILocation(line: 18, column: 23, scope: !35)
!37 = !DILocation(line: 18, column: 5, scope: !31)
!38 = !DILocation(line: 19, column: 17, scope: !39)
!39 = distinct !DILexicalBlock(scope: !35, file: !2, line: 18, column: 39)
!40 = !DILocation(line: 19, column: 49, scope: !39)
!41 = !DILocation(line: 19, column: 42, scope: !39)
!42 = !DILocation(line: 19, column: 25, scope: !39)
!43 = !DILocation(line: 19, column: 23, scope: !39)
!44 = !DILocation(line: 19, column: 15, scope: !39)
!45 = !DILocation(line: 20, column: 5, scope: !39)
!46 = !DILocation(line: 18, column: 32, scope: !35)
!47 = !DILocation(line: 18, column: 34, scope: !35)
!48 = !DILocation(line: 18, column: 30, scope: !35)
!49 = !DILocation(line: 18, column: 5, scope: !35)
!50 = distinct !{!50, !37, !51, !52}
!51 = !DILocation(line: 20, column: 5, scope: !31)
!52 = !{!"llvm.loop.mustprogress"}
!53 = !DILocation(line: 21, column: 26, scope: !18)
!54 = !DILocation(line: 21, column: 5, scope: !18)
!55 = !DILocation(line: 22, column: 5, scope: !18)
!56 = distinct !DISubprogram(name: "scale_and_adjust", scope: !2, file: !2, line: 7, type: !57, scopeLine: 7, flags: DIFlagPrototyped, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !7, retainedNodes: !22)
!57 = !DISubroutineType(types: !58)
!58 = !{!21, !21, !21}
!59 = !DILocalVariable(name: "base", arg: 1, scope: !56, file: !2, line: 7, type: !21)
!60 = !DILocation(line: 7, column: 33, scope: !56)
!61 = !DILocalVariable(name: "limit", arg: 2, scope: !56, file: !2, line: 7, type: !21)
!62 = !DILocation(line: 7, column: 43, scope: !56)
!63 = !DILocalVariable(name: "scaled", scope: !56, file: !2, line: 8, type: !21)
!64 = !DILocation(line: 8, column: 9, scope: !56)
!65 = !DILocation(line: 8, column: 18, scope: !56)
!66 = !DILocation(line: 8, column: 23, scope: !56)
!67 = !DILocation(line: 9, column: 9, scope: !68)
!68 = distinct !DILexicalBlock(scope: !56, file: !2, line: 9, column: 9)
!69 = !DILocation(line: 9, column: 18, scope: !68)
!70 = !DILocation(line: 9, column: 16, scope: !68)
!71 = !DILocation(line: 9, column: 9, scope: !56)
!72 = !DILocation(line: 10, column: 16, scope: !73)
!73 = distinct !DILexicalBlock(scope: !68, file: !2, line: 9, column: 25)
!74 = !DILocation(line: 10, column: 9, scope: !73)
!75 = !DILocation(line: 12, column: 12, scope: !56)
!76 = !DILocation(line: 12, column: 5, scope: !56)
!77 = !DILocation(line: 13, column: 1, scope: !56)
