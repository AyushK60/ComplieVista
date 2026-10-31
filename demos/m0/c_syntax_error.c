/* M0 invalid C fixture: SYNTAX error (missing semicolon). Never compiled to binary; used
   only to verify that real compiler diagnostics are captured verbatim. */
int main(void) {
    int broken = 1
    return broken;
}
