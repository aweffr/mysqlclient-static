/* Deliberately incompatible public functions; the private driver must ignore them. */
#include <stddef.h>
static int calls;
void *SSL_new(void *ctx) { (void)ctx; ++calls; return NULL; }
const char *mysql_get_client_info(void) { return "WRONG_GLOBAL_CLIENT"; }
int collision_call_count(void) { return calls; }
