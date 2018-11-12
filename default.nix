{ stdenv
, ros_comm
, mkRosPackage
, python3Packages
}:

mkRosPackage rec {
  name = "${pname}-${version}";
  pname = "robonomics_comm";
  version = "0.3.0";

  src = ./.;

  propagatedBuildInputs = with python3Packages;
  [ ros_comm web3 base58 voluptuous ipfsapi ];

  meta = with stdenv.lib; {
    description = "Robonomics communication stack";
    homepage = http://github.com/airalab/robonomics_comm;
    license = licenses.bsd3;
    maintainers = [ maintainers.akru ];
  };
}
