/* Linker error: calls a function that is declared but never defined. */
void missing_function(void);

int main(void) {
    missing_function();
    return 0;
}
