import shlex
import subprocess
import optparse
import json
import os
import shutil
import pyproct.tools.commonTools as tools
import pyproct.tools.scriptTools as s_tools
import tarfile

def execute_pyproct(script):
    STDOUT_FILE = "test.out"
    STDERR_FILE = "test.err"
    args = shlex.split("python -m pyproct.main %s"%script)
    stdout_handler = open(STDOUT_FILE, "w")
    stderr_handler = open(STDERR_FILE, "w")
    p = subprocess.Popen(args, stdout= stdout_handler, stderr= stderr_handler)
    p.wait()
    stdout_handler.close()
    stderr_handler.close()
    return STDOUT_FILE, STDERR_FILE

def clean(workspace):
    # Delete everything
    for subpath in ["matrix", "results", "clusters", "tmp"]:
        try:
            shutil.rmtree(workspace[subpath], ignore_errors = True)
        except Exception:
            pass
    shutil.rmtree(workspace["base"], ignore_errors = True)

def diff_is_not_empty(file1, file2):
    args = shlex.split("diff %s %s"%(file1, file2))
    p = subprocess.Popen(args, stdout= subprocess.PIPE)
    p.wait()
    return len(p.stdout.read()) != 0

if __name__ == "__main__":
    parser = optparse.OptionParser(usage='%prog --test_file X (--action [TEST]/GENERATE]) (--log X)',version='1.0')

    parser.add_option('--action', action = "store",
                                  default = "TEST",
                                  dest = "action",
                                  metavar = "TEST",
                                  help="Chooses whether to test or to generate results for the regression tests")

    parser.add_option('--log', action = "store",
                                  default = "regression_test_log.txt",
                                  dest = "log_file",
                                  metavar = "regression_test_log.txt",
                                  help="Name of the log file that will be generated when using --action TEST.")


    options, args = parser.parse_args()
    input_file = args[0]
    control_info = json.loads(open(input_file, "r").read())

    print "Options.action = %s" % options.action
    # Generate regression tests
    if options.action == "GENERATE":
        for test_info in control_info:
            stdout_file, stderr_file = execute_pyproct(test_info["script"])
            print "STDOUT: \n%s" % stdout_file
            script = json.loads(tools.remove_comments(open(test_info["script"], "r").read()))
            workspace = script["global"]["workspace"]
            s_tools.create_directory(test_info["expected_results_dir"])

            # Move the generated files
            os.system("mv %s %s %s"%(stdout_file, stderr_file,test_info["expected_results_dir"]))
            for subpath in test_info["files_to_check"]:
                for file in test_info["files_to_check"][subpath]:
                    os.system("mv %s %s"%(os.path.join(workspace["base"],subpath,file),
                                                       test_info["expected_results_dir"]))

            clean(workspace)

    # Execute regression tests
    elif options.action == "TEST":
        log_handler = open(options.log_file,"w")

        global_test_outcome = True

        for test_info in control_info:
            log_handler.write("- Performing %s test ... \n"%test_info["name"])

            try:
                stdout_file, stderr_file = execute_pyproct(test_info["script"])
                print "STDOUT: \n%s" % stdout_file
                script = json.loads(tools.remove_comments(open(test_info["script"], "r").read()))
                workspace = script["global"]["workspace"]

                test_outcome = True

                for file_path in [stdout_file, stderr_file]:
                    expected_file_path = os.path.join(test_info["expected_results_dir"], file_path)
                    if diff_is_not_empty(file_path, expected_file_path):
                        log_handler.write("\t- Different files: %s and %s \n"%(file_path, expected_file_path))
                        test_outcome = False
                os.system("rm %s %s"%(stdout_file, stderr_file))

                for subpath in test_info["files_to_check"]:
                    for file in test_info["files_to_check"][subpath]:
                        file_path = os.path.join(workspace["base"],subpath,file)
                        expected_file_path = os.path.join(test_info["expected_results_dir"], file)
                        if diff_is_not_empty(file_path, expected_file_path):
                            log_handler.write("\t- Different files: %s and %s \n"%(file_path, expected_file_path))
                            test_outcome = False
            except Exception:
                test_outcome = False
                log_handler.write("\t- Test failed due to unknown exception. \n")
            finally:
                if test_outcome == False:
                    log_handler.write("\t FAILED\n")
                else:
                    log_handler.write("\t OK\n")

            global_test_outcome = test_outcome and global_test_outcome

        log_handler.close()
        clean(workspace)

        if global_test_outcome == True:
            print "All tests are OK"
        else:
            print "Some tests failed. Please review %s to know more about it."%options.log_file

    elif options.action == "INFLATE_DATA":
        base_folder = "Data"
        extraction_folder = "files"
        for data_info in control_info:
            tar = tarfile.open(data_info["source"])
            file_names = tar.getnames()
            tar.extractall(path = os.path.join(base_folder, extraction_folder))
            tar.close()
            list_file = open(os.path.join(base_folder, extraction_folder,"%s.lst"%data_info["name"]),"w")
            for name in file_names:
                list_file.write('"%s"\n'%data_info["name"])

    else:
        print "Unknown action %s"%options.action

