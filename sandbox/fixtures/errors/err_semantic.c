/* Semantic error: undeclared identifier (clang -fsyntax-only diagnostic). */
int main(void) {
    int ok = 1;
    return ok + undefined_value;
}
