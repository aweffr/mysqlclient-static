#!/usr/bin/env bash
set -euo pipefail
ROOT=$(pwd)
SRC="$ROOT/.work/sources"
PREFIX=${MCS_PREFIX:-/opt/mysqlclient-static}
JOBS=${JOBS:-4}
if [[ $(uname -s) == Darwin ]]; then
  OPENSSL_TARGET=darwin64-arm64-cc
  ARCH_FLAGS="-arch arm64"
  export MACOSX_DEPLOYMENT_TARGET=11.0
else
  OPENSSL_TARGET=linux-x86_64
  ARCH_FLAGS="-march=x86-64 -mtune=generic"
fi
export CFLAGS="-O2 -fPIC -fvisibility=hidden $ARCH_FLAGS"
export CXXFLAGS="$CFLAGS"
mkdir -p "$PREFIX" reports/native
(
  cd "$SRC/openssl"
  ./Configure "$OPENSSL_TARGET" no-shared no-module no-dso no-engine no-legacy no-tests \
    no-autoload-config --prefix="$PREFIX" --libdir=lib --openssldir=/etc/ssl
  make -j"$JOBS"
  make install_sw
) 2>&1 | tee reports/native/openssl.log
(
  cd "$SRC/zlib"
  ./configure --static --prefix="$PREFIX"
  make -j"$JOBS"
  make install
) 2>&1 | tee reports/native/zlib.log
# Disable optional weak tracing hooks; never link the distribution's zstd.a.
cmake -S "$SRC/zstd/build/cmake" -B .work/zstd-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_C_FLAGS="$CFLAGS -DZSTD_TRACE=0" \
  -DZSTD_BUILD_SHARED=OFF -DZSTD_BUILD_STATIC=ON \
  -DZSTD_BUILD_PROGRAMS=OFF -DZSTD_BUILD_TESTS=OFF -DZSTD_MULTITHREAD_SUPPORT=OFF \
  2>&1 | tee reports/native/zstd.log
cmake --build .work/zstd-build -j "$JOBS" 2>&1 | tee -a reports/native/zstd.log
cmake --install .work/zstd-build 2>&1 | tee -a reports/native/zstd.log
cmake -S "$SRC/connector" -B .work/connector-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_C_FLAGS="$CFLAGS" \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.12 \
  -DWITH_SSL=OPENSSL -DOPENSSL_USE_STATIC_LIBS=TRUE \
  -DOPENSSL_ROOT_DIR="$PREFIX" -DOPENSSL_INCLUDE_DIR="$PREFIX/include" \
  -DOPENSSL_SSL_LIBRARY="$PREFIX/lib/libssl.a" \
  -DOPENSSL_CRYPTO_LIBRARY="$PREFIX/lib/libcrypto.a" \
  -DWITH_EXTERNAL_ZLIB=ON -DZLIB_INCLUDE_DIR="$PREFIX/include" \
  -DZLIB_LIBRARY="$PREFIX/lib/libz.a" \
  -DZSTD_INCLUDE_DIRS="$PREFIX/include" -DZSTD_LIBRARIES="$PREFIX/lib/libzstd.a" \
  -DWITH_CURL=OFF -DWITH_UNIT_TESTS=OFF -DWITH_MYSQLCOMPAT=ON \
  -DCLIENT_PLUGIN_CACHING_SHA2_PASSWORD=STATIC \
  -DCLIENT_PLUGIN_SHA256_PASSWORD=STATIC \
  -DCLIENT_PLUGIN_MYSQL_NATIVE_PASSWORD=STATIC \
  -DCLIENT_PLUGIN_MYSQL_CLEAR_PASSWORD=OFF \
  -DCLIENT_PLUGIN_AUTH_GSSAPI_CLIENT=OFF \
  -DCLIENT_PLUGIN_CLIENT_ED25519=OFF -DCLIENT_PLUGIN_PARSEC=OFF \
  -DCLIENT_PLUGIN_DIALOG=OFF \
  -DCLIENT_PLUGIN_ZSTD=STATIC -DCLIENT_PLUGIN_ZLIB=STATIC \
  -DDEFAULT_SSL_VERIFY_SERVER_CERT=ON \
  2>&1 | tee reports/native/connector.log
cmake --build .work/connector-build -j "$JOBS" 2>&1 | tee -a reports/native/connector.log
cmake --install .work/connector-build 2>&1 | tee -a reports/native/connector.log
# Guard against silently ignored misspelled plugin options.
ARCHIVE=$(find "$PREFIX" -name libmariadb.a -type f -print -quit)
if [[ -z "$ARCHIVE" ]]; then ARCHIVE=$(find "$PREFIX" -name libmariadbclient.a -type f -print -quit); fi
test -n "$ARCHIVE"
nm "$ARCHIVE" > reports/native/connector-symbols.txt
grep -q 'caching_sha2_password_client_plugin' reports/native/connector-symbols.txt
grep -q 'sha256_password_client_plugin' reports/native/connector-symbols.txt
printf '%s\n' "$ARCHIVE" > .work/connector-archive.txt
cp "$ARCHIVE" "$PREFIX/lib/libmysqlclient-static.a"
cp "$ROOT/ci/exports.map" "$PREFIX/exports.map"
# No shared objects are needed by the wheel build, regardless of CMake install outputs.
find "$PREFIX" -type f -name '*.so*' -delete
