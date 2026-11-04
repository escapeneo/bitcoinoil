package=native_ds_store
$(package)_version=1.3.0
$(package)_download_path=https://github.com/dmgbuild/ds_store/archive/
$(package)_file_name=v$($(package)_version).tar.gz
$(package)_sha256_hash=76b3280cd4e19e5179defa23fb594a9dd32643b0c80d774bd3108361d94fb46d
$(package)_install_libdir=$(build_prefix)/lib/python3/dist-packages

# Pure Python, used by contrib/macdeploy/macdeployqtplus; copied as is.
define $(package)_stage_cmds
    mkdir -p $($(package)_staging_dir)$($(package)_install_libdir) && \
    cp -r ds_store $($(package)_staging_dir)$($(package)_install_libdir)/
endef
