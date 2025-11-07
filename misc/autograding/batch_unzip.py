import os
import zipfile


def main():
    n_success = 0
    n_failure = 0
    anormalies = set()
    done = set()
    for filename in os.listdir("./zips"):
        if filename.endswith(".zip"):
            print(f"Unzipping {filename}")
            filepath = os.path.join("./zips", filename)
            try:
                with zipfile.ZipFile(filepath, "r") as zip_ref:
                    tgt_dirname = f"./student_files/{filename.split('_')[0]}"

                    if tgt_dirname in done:
                        print(f"[!] {tgt_dirname} already unzipped")
                        continue
                    done.add(tgt_dirname)

                    zip_ref.extractall(tgt_dirname)
                    n_success += 1
            except Exception as e:
                print(f"[!] Error unzipping {filename}: {e}")
                n_failure += 1
                continue
        else:
            anormalies.add(f"./zips/{filename}")
            n_failure += 1

    print(f"Processed {n_success} files")
    print(f"Failed to process {n_failure} files ({len(anormalies)} non-zip files)")
    print(f"Anormalies: {list(sorted(anormalies))}")


if __name__ == "__main__":
    main()
